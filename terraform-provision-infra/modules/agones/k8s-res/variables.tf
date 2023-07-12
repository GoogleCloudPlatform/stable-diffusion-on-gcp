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

variable "oauth_client_id" {
  description = "OAuth Client ID."
  type        = string
}

variable "oauth_client_secret" {
  description = "OAuth Client Secret."
  type        = string
}
variable "sd_webui_domain" {
  description = "you owned sub domain for stable diffusion webui access."
  type        = string
}
variable "gke_cluster_name" {
  description = "GKE Cluster Name."
  type        = string
}
variable "gke_cluster_location" {
  description = "GKE Cluster Location"
  type        = string
}
variable "project_id" {
  description = "GCP project id"
  type        = string
}
variable "google_filestore_reserved_ip_range" {
  description = "GCP project id"
  type        = string
}
variable "gke_cluster_nodepool" {
  description = "GCP project id"
  type        = string
}
variable "nginx_image_url" {
  description = "Nginx Image url"
  type        = string
}
variable "webui_image_url" {
  description = "Stable diffusion webui Image url"
  type        = string
}
variable "game_server_image_url" {
  description = "Stable diffusion webui Image url"
  type        = string
  default     = "us-docker.pkg.dev/agones-images/examples/simple-game-server:0.14"
}
variable "webui_address_name" {
  description = "GCP project id"
  type        = string
}