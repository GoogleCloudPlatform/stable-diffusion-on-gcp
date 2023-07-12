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
    null = {
      source  = "hashicorp/null"
      version = "3.2.1"
    }
  }
}
resource "null_resource" "build_webui_image" {
  provisioner "local-exec" {
    command     = "gcloud builds submit --machine-type=e2-highcpu-32 --disk-size=100 --region=us-central1 -t ${var.artifact_registry}/${var.sd_webui_image.tag}"
    working_dir = var.sd_webui_image.path
  }
}