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
variable "gke_cluster_nodepool" {
  description = "GCP project id"
  type        = string
}