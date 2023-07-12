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

# Input variable definitions
variable "project_id" {
  description = "Project ID of the cloud resource."
  type        = string
}

variable "region" {
  description = "Region to set for gcp resource deploy."
  type        = string
}
variable "filestore_zone" {
  description = "Zone to set for filestore nfs server, should be same zone with gke node."
  type        = string
}

variable "cluster_location" {
  description = "gke cluster location choose a zone or region."
  type        = string
}
variable "node_machine_type" {
  description = "gke node machine type."
  type        = string
  default     = "custom-12-49152-ext"
}

variable "accelerator_type" {
  description = "Get available accelerator_type from gcloud compute accelerator-types list --format='csv(zone,name)' "
  type        = string
  default     = "nvidia-tesla-t4"
}
variable "gke_num_nodes" {
  description = "Tags to set on the bucket."
  type        = number
  default     = 1
}
variable "skip_build_image" {
  description = "Choose if build images."
  type        = bool
  default     = false
}
variable "gcp_service_list" {
  description = "The list of apis necessary for the project"
  type        = list(string)
  default = [
    "artifactregistry.googleapis.com",
    "cloudbuild.googleapis.com",
    "compute.googleapis.com",
    "container.googleapis.com",
    "file.googleapis.com",
    "networkmanagement.googleapis.com",
    "memcache.googleapis.com",
    "cloudfunctions.googleapis.com",
    "cloudscheduler.googleapis.com",
    "iap.googleapis.com",
    "dns.googleapis.com",
    "redis.googleapis.com",
    "vpcaccess.googleapis.com"
  ]
}
variable "webui_dockerfile_path" {
  description = "Dockerfile path for webui fleet"
  type        = string
  default     = ""
}
variable "cloudfunctions_source_code_path" {
  description = "Dockerfile path for webui fleet"
  type        = string
  default     = "../Stable-Diffusion-UI-Agones/cloud-function/"
}
