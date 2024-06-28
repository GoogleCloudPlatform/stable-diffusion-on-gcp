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
    helm = {
      source  = "hashicorp/helm"
      version = "~> 2.3"
    }
  }
}
data "google_client_config" "default" {}

data "google_container_cluster" "my_cluster" {
  name     = var.gke_cluster_name
  location = var.gke_cluster_location
  project  = var.project_id
}

provider "kubernetes" {
  host  = "https://${data.google_container_cluster.my_cluster.endpoint}"
  token = data.google_client_config.default.access_token
  cluster_ca_certificate = base64decode(
    data.google_container_cluster.my_cluster.master_auth[0].cluster_ca_certificate,
  )
  experiments {
    manifest_resource = true
  }
}

provider "helm" {
  kubernetes {
    host  = "https://${data.google_container_cluster.my_cluster.endpoint}"
    token = data.google_client_config.default.access_token
    cluster_ca_certificate = base64decode(
      data.google_container_cluster.my_cluster.master_auth[0].cluster_ca_certificate,
    )
  }
}

resource "helm_release" "agones" {
  name             = "agones"
  repository       = "https://agones.dev/chart/stable"
  chart            = "agones"
  force_update     = true
  namespace        = "agones-system"
  create_namespace = true
  version          = var.agones_version
  values = [
    file("../Stable-Diffusion-UI-Agones/agones/values.yaml")
  ]
  set {
    name  = "agones.controller.nodeSelector.cloud\\.google\\.com/gke-nodepool"
    value = var.gke_cluster_nodepool
    type  = "string"
  }
  set {
    name  = "agones.ping.nodeSelector.cloud\\.google\\.com/gke-nodepool"
    value = var.gke_cluster_nodepool
    type  = "string"
  }
  set {
    name  = "agones.allocator.nodeSelector.cloud\\.google\\.com/gke-nodepool"
    value = var.gke_cluster_nodepool
    type  = "string"
  }
  set {
    name  = "agones.extensions.nodeSelector.cloud\\.google\\.com/gke-nodepool"
    value = var.gke_cluster_nodepool
    type  = "string"
  }
}