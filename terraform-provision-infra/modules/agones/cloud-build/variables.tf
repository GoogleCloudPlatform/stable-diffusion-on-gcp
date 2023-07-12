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

variable "nginx_image" {
  description = "Region to set for gcp resource deploy."
  type = object({
    path = string
    tag  = string
  })
  default = {
    path = "../Stable-Diffusion-UI-Agones/nginx/"
    tag  = "nginx:tf"
  }
}
variable "sd_webui_image" {
  description = "Region to set for gcp resource deploy."
  type = object({
    path = string
    tag  = string
  })
  default = {
    path = "../Stable-Diffusion-UI-Agones/sd-webui/"
    tag  = "sd-webui:tf"
  }
}
variable "game_server_image" {
  description = "Region to set for gcp resource deploy."
  type = object({
    path = string
    tag  = string
  })
  default = {
    path = "../Stable-Diffusion-UI-Agones/agones-sidecar/"
    tag  = "game-server:tf"
  }
}
variable "artifact_registry" {
  type        = string
  description = "artifact registry URL."
}