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
  ip_cidr_range = "10.0.0.0/16"
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
  name       = "tf-gen-nat-${random_id.tf_subfix.hex}-ip-${count.index}"
  region     = google_compute_subnetwork.subnet.region
  depends_on = [google_project_service.gcp_services]
}

# NAT Gateway
resource "google_compute_router_nat" "nat" {
  name                               = "tf-gen-${var.region}-nat-gw-${random_id.tf_subfix.hex}"
  router                             = google_compute_router.router.name
  region                             = google_compute_router.router.region
  nat_ip_allocate_option             = "MANUAL_ONLY"
  nat_ips                            = google_compute_address.address.*.self_link
  source_subnetwork_ip_ranges_to_nat = "ALL_SUBNETWORKS_ALL_IP_RANGES"
}

# GKE cluster
resource "google_container_cluster" "gke" {
  name                     = "tf-gen-gke-${random_id.tf_subfix.hex}"
  location                 = var.filestore_zone
  remove_default_node_pool = true
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
resource "google_container_node_pool" "separately_gpu_nodepool" {
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

    spot  = true
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
  repository_id = "${random_id.tf_subfix.hex}-stable-diffusion-repository"
  description   = "stable diffusion repository"
  format        = "DOCKER"
  depends_on    = [google_project_service.gcp_services]
}