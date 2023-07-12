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

# cloud build image
gcloud builds submit --config cloud-build-config-diffusers.yaml .

#creat hp-tuning job
gcloud ai hp-tuning-jobs create  \
   --region=us-central1 \
   --display-name=sd-diffusers-hpo \
   --max-trial-count=5 \
   --parallel-trial-count=2 \
   --config=vertex-config-diffusers.yaml