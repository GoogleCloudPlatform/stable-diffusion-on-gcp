# Copyright 2023 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "4.63.1"
    }
    random = {
      source  = "hashicorp/random"
      version = "3.5.1"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "2.3.0"
    }
  }
}
provider "google" {
  project = var.project_id
  region  = var.region
}
resource "random_id" "tf_subfix" {
  byte_length = 4
}
# Enable related service
resource "google_project_service" "gcp_services" {
  for_each                   = toset(var.gcp_service_list)
  project                    = var.project_id
  service                    = each.key
  disable_dependent_services = false
  disable_on_destroy         = false
}

data "google_compute_default_service_account" "default" {
  depends_on = [google_project_service.gcp_services]
}

data "archive_file" "lambda_my_function" {
  type             = "zip"
  source_dir       = var.cloudfunctions_source_code_path
  output_file_mode = "0666"
  output_path      = "./cloud_function.zip"
}

# VPC
resource "google_compute_network" "vpc" {
  project                 = var.project_id
  name                    = "tf-gen-vpc-${random_id.tf_subfix.hex}"
  auto_create_subnetworks = "false"
  depends_on              = [google_project_service.gcp_services]
}

# Subnet
resource "google_compute_subnetwork" "subnet" {
  name          = "tf-gen-subnet-${random_id.tf_subfix.hex}"
  region        = var.region
  network       = google_compute_network.vpc.name
  ip_cidr_range = "10.10.0.0/16"
}

# Cloud Router
resource "google_compute_router" "router" {
  name    = "tf-gen-router-${var.region}-${random_id.tf_subfix.hex}"
  region  = google_compute_subnetwork.subnet.region
  network = google_compute_network.vpc.id
}
# NAT IP
resource "google_compute_address" "address" {
  count      = 2
  name       = "nat-${random_id.tf_subfix.hex}-ip-${count.index}"
  region     = google_compute_subnetwork.subnet.region
  depends_on = [google_project_service.gcp_services]
}

resource "google_compute_global_address" "webui_addr" {
  name       = "sd-webui-ingress-${random_id.tf_subfix.hex}"
  depends_on = [google_project_service.gcp_services]
}

# NAT Gateway
resource "google_compute_router_nat" "nat" {
  name                               = "tf-gen-${var.region}-nat-gw"
  router                             = google_compute_router.router.name
  region                             = google_compute_router.router.region
  nat_ip_allocate_option             = "MANUAL_ONLY"
  nat_ips                            = google_compute_address.address.*.self_link
  source_subnetwork_ip_ranges_to_nat = "ALL_SUBNETWORKS_ALL_IP_RANGES"
}

# GKE cluster
resource "google_container_cluster" "gke" {
  name                     = "tf-gen-gke-${random_id.tf_subfix.hex}"
  location                 = var.cluster_location
  remove_default_node_pool = false
  enable_shielded_nodes    = true
  initial_node_count       = 1
  network                  = google_compute_network.vpc.name
  subnetwork               = google_compute_subnetwork.subnet.name
  private_cluster_config {
    enable_private_nodes   = true
    master_ipv4_cidr_block = "192.168.1.0/28"
  }
  ip_allocation_policy {
  }
  monitoring_config {
    enable_components = ["SYSTEM_COMPONENTS", "APISERVER", "SCHEDULER", "CONTROLLER_MANAGER"]
    managed_prometheus { enabled = true }
  }
  logging_config {
    enable_components = ["SYSTEM_COMPONENTS", "WORKLOADS", "APISERVER", "SCHEDULER", "CONTROLLER_MANAGER"]
  }
  release_channel {
    channel = "STABLE"
  }
  maintenance_policy {
    daily_maintenance_window {
      start_time = "03:00"
    }
  }
  addons_config {
    http_load_balancing {
      disabled = false
    }
    horizontal_pod_autoscaling {
      disabled = false
    }
    gcp_filestore_csi_driver_config {
      enabled = true
    }
    gce_persistent_disk_csi_driver_config {
      enabled = true
    }
    dns_cache_config {
      enabled = true
    }
  }
  node_config {
    shielded_instance_config {
      enable_secure_boot          = true
      enable_integrity_monitoring = true
    }
  }
  lifecycle {
    ignore_changes = all
  }
}

# Separately Managed Node Pool
resource "google_container_node_pool" "gpu_nodepool" {
  name     = "${var.accelerator_type}-nodepool"
  location = var.cluster_location
  cluster  = google_container_cluster.gke.name
  autoscaling {
    min_node_count = 1
    max_node_count = 10
  }
  node_count = var.gke_num_nodes
  node_config {
    oauth_scopes = [
      "https://www.googleapis.com/auth/cloud-platform"
    ]

    labels = {
      Terraform   = "true"
      Environment = "dev"
    }

    preemptible  = true
    machine_type = var.node_machine_type
    image_type   = "COS_CONTAINERD"
    gcfs_config {
      enabled = true
    }
    guest_accelerator {
      type  = var.accelerator_type
      count = 1
      gpu_sharing_config {
        gpu_sharing_strategy       = "TIME_SHARING"
        max_shared_clients_per_gpu = 2
      }
    }
    disk_type    = "pd-balanced"
    disk_size_gb = 100

    tags = ["gpu-node", "gke-sd"]
    metadata = {
      disable-legacy-endpoints = "true"
    }
    shielded_instance_config {
      enable_secure_boot          = true
      enable_integrity_monitoring = true
    }
  }
  lifecycle {
    ignore_changes = all
  }
}
#agones firewall
resource "google_compute_firewall" "agones" {
  depends_on = [google_container_cluster.gke]
  name       = "allow-agones-${random_id.tf_subfix.hex}"
  network    = google_compute_network.vpc.name
  project    = var.project_id
  allow {
    protocol = "tcp"
    ports    = ["443", "8080", "8081"]
  }
  source_ranges = ["0.0.0.0/0"]
}
# Filestore
resource "google_filestore_instance" "instance" {
  name     = "nfs-store-${random_id.tf_subfix.hex}"
  location = var.filestore_zone
  tier     = "BASIC_HDD"
  file_shares {
    capacity_gb = 1024
    name        = "vol1"
  }
  networks {
    network = google_compute_network.vpc.name
    modes   = ["MODE_IPV4"]
  }
}
#Artifact Registry
resource "google_artifact_registry_repository" "sd_repo" {
  location      = var.region
  repository_id = "sd-repository-${random_id.tf_subfix.hex}"
  description   = "stable diffusion repository"
  format        = "DOCKER"
  depends_on    = [google_project_service.gcp_services]
}
# Redis cache
resource "google_redis_instance" "cache" {
  region             = var.region
  name               = "sd-agones-cache-${random_id.tf_subfix.hex}"
  tier               = "BASIC"
  memory_size_gb     = 1
  authorized_network = google_compute_network.vpc.id
  redis_version      = "REDIS_6_X"
  display_name       = "Stable Diffusion Agones Cache Instance"
  connect_mode       = "DIRECT_PEERING"
  maintenance_policy {
    weekly_maintenance_window {
      day = "SUNDAY"
      start_time {
        hours   = 0
        minutes = 30
        seconds = 0
        nanos   = 0
      }
    }
  }
}
# vpc_connector_for_function
resource "google_vpc_access_connector" "connector" {
  name          = "vpc-con-${random_id.tf_subfix.hex}"
  ip_cidr_range = "192.168.240.16/28"
  network       = google_compute_network.vpc.name
}
# function_source_gcs_bucket
resource "google_storage_bucket" "bucket" {
  name                        = "cloud-function-source-${random_id.tf_subfix.hex}"
  project                     = var.project_id
  location                    = var.region
  force_destroy               = true
  storage_class               = "COLDLINE"
  uniform_bucket_level_access = true
  depends_on                  = [google_project_service.gcp_services]
}
# function_source_zip
resource "google_storage_bucket_object" "archive" {
  name   = "cloud_function.zip"
  bucket = google_storage_bucket.bucket.name
  source = "./cloud_function.zip"
}

resource "google_cloudfunctions_function" "function" {
  name                          = "redis-http-${random_id.tf_subfix.hex}"
  description                   = "agones gpu pod recycle function"
  runtime                       = "python310"
  trigger_http                  = true
  region                        = var.region
  ingress_settings              = "ALLOW_INTERNAL_AND_GCLB"
  vpc_connector                 = google_vpc_access_connector.connector.name
  vpc_connector_egress_settings = "PRIVATE_RANGES_ONLY"
  entry_point                   = "redis_http"
  environment_variables = {
    REDIS_HOST    = google_redis_instance.cache.host
    TIME_INTERVAL = 900
  }
  available_memory_mb   = 128
  source_archive_bucket = google_storage_bucket.bucket.name
  source_archive_object = google_storage_bucket_object.archive.name
  timeout               = 60
  depends_on            = [google_storage_bucket_object.archive]
}

resource "google_cloudfunctions_function_iam_member" "invoker" {
  project        = google_cloudfunctions_function.function.project
  region         = google_cloudfunctions_function.function.region
  cloud_function = google_cloudfunctions_function.function.name

  role       = "roles/cloudfunctions.invoker"
  member     = "serviceAccount:${data.google_compute_default_service_account.default.email}"
  depends_on = [google_project_service.gcp_services]
}

resource "google_cloud_scheduler_job" "job" {
  name        = "sd-agones-cruiser-${random_id.tf_subfix.hex}"
  description = "cloud function http schedule job"
  region      = var.region
  schedule    = "*/5 * * * *"
  http_target {
    http_method = "GET"
    uri         = google_cloudfunctions_function.function.https_trigger_url
    oidc_token {
      service_account_email = data.google_compute_default_service_account.default.email
    }
  }
  depends_on = [google_project_service.gcp_services]
}

resource "google_dns_managed_zone" "private_zone" {
  name        = "private-zone-${random_id.tf_subfix.hex}"
  dns_name    = "private.domain."
  description = "Example private DNS zone"
  visibility  = "private"
  private_visibility_config {
    networks {
      network_url = google_compute_network.vpc.id
    }
  }
  depends_on = [google_project_service.gcp_services]
}

resource "google_dns_record_set" "redis_a" {
  name         = "redis.${google_dns_managed_zone.private_zone.dns_name}"
  managed_zone = google_dns_managed_zone.private_zone.name
  type         = "A"
  ttl          = 300
  rrdatas      = [google_redis_instance.cache.host]
}