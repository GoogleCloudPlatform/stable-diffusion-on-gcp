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
gcloud builds submit --config cloud-build-config.yaml .

# create vertex ai customer training job
# args format:
# --model_name: Huggingface repo id, or "/gcs/bucket_name/model_folder". I only test the models downloaded from HF, with standard diffusers format. Safetensors has not been test.
# --input_storage: /gcs/bucket_name/input_image_folder
#     for dreambooth: just put images in the image folder
#     for text-to-image: put images and metadata.jsonl in the image folder
# --output_storage: /gcs/bucket_name/output_folder
# --prompt: a photo of XXX
# --set_grads_to_none: for training dreambooth on T4
# input_storage, output_storage, and prompt are required arguments
gcloud ai custom-jobs create \
  --region=us-central1 \
  --display-name=sd-diffuser-t2i-1v100 \
  --config=vertex-config-nfs.yaml \
  --args="--method=diffuser_text_to_image,--model_name=CompVis/stable-diffusion-v1-4,--input_storage=/gcs/sd/input_dog_t2i,--output_storage=/gcs/sd/diffusers_t2i_output,--resolution=512,--batch_size=1,--lr=1e-4,--use_8bit=True,--max_train_steps=100" \
  --command="python3,train.py"

gcloud ai custom-jobs create \
  --region=us-central1 \
  --display-name=sd-diffuser-dreambooth-1v100 \
  --config=vertex-config-nfs.yaml \
  --args="--method=diffuser_dreambooth,--model_name=runwayml/stable-diffusion-v1-5,--input_storage=/gcs/sd/dog_image,--output_storage=/gcs/sd/diffusers_db_output,--prompt=a photo of sks dog,--class_prompt=a photo of dog,--num_class_images=50,--lr=1e-4,--use_8bit=True,--max_train_steps=100,--text_encoder=True,--set_grads_to_none=True" \
  --command="python3,train.py"

# only save the models in GCS to Filestore
gcloud ai custom-jobs create  \
  --region=us-central1   \
  --display-name=sd-diffusers   \
  --config=vertex-config-nfs.yaml   \
  --args="--output_storage=/gcs/sd/diffusers_output,--save_nfs_only=True" \
  --command="python3,train.py"
