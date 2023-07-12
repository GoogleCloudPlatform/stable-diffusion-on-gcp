# Copyright 2023 Google LLC All Rights Reserved.
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

import yaml
import kfp
import subprocess
from datetime import datetime
from kfp.v2 import dsl
from kfp.v2 import compiler
from kfp.v2.dsl import Condition
from typing import NamedTuple
from kfp.v2.dsl import (Artifact, Dataset, Input, InputPath, Model, Output,
                        OutputPath, component)
from google.cloud import aiplatform
import google.cloud.aiplatform as aip
from google_cloud_pipeline_components import aiplatform as gcc_aip
from google_cloud_pipeline_components.experimental.custom_job import CustomTrainingJobOp


print("parsing pipeline configuration")
with open('pipeline_conf.yml') as f:
    try:
        pipeline_conf = yaml.safe_load(f)
    except yaml.YAMLError as exc:
        print(exc)

print("loading configuration")
PIPELINE_NAME = pipeline_conf['pipelineName']
BUILD_IMAGE = str(pipeline_conf['buildImage'])
PROJECT_NUMBER = pipeline_conf['gcpSpecs']['project_number']
PROJECT_ID = pipeline_conf['gcpSpecs']['project_id']
REGION = pipeline_conf['gcpSpecs']['region']
IMAGE_URI = pipeline_conf['vertexSpecs']['workerPoolSpecs']['containerSpec']['imageUri']
NFS_ENABLE = pipeline_conf['NFS']['enable']
NFS_IP = pipeline_conf['NFS']['server']
NFS_PATH = pipeline_conf['NFS']['path']
NFS_MOUNT = pipeline_conf['NFS']['mountPoint']
PIPELINE_BUCKET = pipeline_conf['gcpSpecs']['pipeline_bucket']
MACHINE_TYPE = pipeline_conf['vertexSpecs']['workerPoolSpecs']['machineSpec']['machineType']
MACHINE_NUM = pipeline_conf['vertexSpecs']['workerPoolSpecs']['replicaCount']
GPU_TPYE = pipeline_conf['vertexSpecs']['workerPoolSpecs']['machineSpec']['acceleratorType']
GPU_NUM = pipeline_conf['vertexSpecs']['workerPoolSpecs']['machineSpec']['acceleratorCount']
CODE_INPUT_DIR = f"/gcs/{PIPELINE_BUCKET}/code".format(PIPELINE_BUCKET)
DATA_INPUT_DIR = pipeline_conf['modelSpecs']['input_storage']
MODEL_OUTPUT_DIR = pipeline_conf['modelSpecs']['output_storage']



TRAIN_ARGS = []
for k,v in pipeline_conf['modelSpecs'].items():
    if ((v != None ) and (v != "")):
        TRAIN_ARGS.append("--"+k)
        TRAIN_ARGS.append(v)
    else:
        pass

if GPU_TPYE == "NVIDIA_TESLA_V100":
    accelerator_type = aip.gapic.AcceleratorType.NVIDIA_TESLA_V100
elif GPU_TPYE == "NVIDIA_TESLA_A100":
    accelerator_type = aip.gapic.AcceleratorType.NVIDIA_TESLA_A100
elif GPU_TPYE == "NVIDIA_TESLA_T4":
    accelerator_type = aip.gapic.AcceleratorType.NVIDIA_TESLA_T4
else:
    print("No GPU type specified")

BUCKET_URI = f"gs://{PIPELINE_BUCKET}"
PIPELINE_ROOT = f"{BUCKET_URI}/pipeline_root/{PIPELINE_NAME}".format(BUCKET_URI,PIPELINE_NAME)
"""
if NFS_ENABLE == True:
    job_spec=[{
            "containerSpec": {
                "args": TRAIN_ARGS,
                "imageUri": f"{IMAGE_URI}".format(),
            },
            "replicaCount": "1",
            "machineSpec": {
                "machineType": f"{MACHINE_TYPE}",
                "accelerator_type": f"aip.gapic.AcceleratorType.{GPU_TPYE}".format(GPU_TPYE),
                "accelerator_count": GPU_NUM,
            },
        }]
else:
    job_spec=[{
            "containerSpec": {
                "args": ["--model_name", "runwayml/stable-diffusion-v1-5", "--input_storage", f"{DATA_INPUT_DIR}", "--output_storage", f"{MODEL_OUTPUT_DIR}", "--prompt", "a photo of sks dog"],
                "imageUri": f"{IMAGE_URI}".format(),
            },
            "replicaCount": "1",
            "machineSpec": {
                "machineType": f"{MACHINE_TYPE}",
                "accelerator_type": f"aip.gapic.AcceleratorType.{GPU_TPYE}".format(GPU_TPYE),
                "accelerator_count": GPU_NUM,
            },
        }]

"""

job_spec_default=[{
        "containerSpec": {
            "args": TRAIN_ARGS,
            "imageUri": f"{IMAGE_URI}".format(),
        },
        "replicaCount": MACHINE_NUM,
        "machineSpec": {
            "machineType": f"{MACHINE_TYPE}",
            "accelerator_type": accelerator_type,
            "accelerator_count": GPU_NUM,
        },
    }]

job_spec_nfs=[{
        "containerSpec": {
            "args": TRAIN_ARGS,
            "imageUri": f"{IMAGE_URI}".format(),
        },
        "replicaCount": "1",
        "machineSpec": {
            "machineType": f"{MACHINE_TYPE}",
            "accelerator_type": accelerator_type,
            "accelerator_count": GPU_NUM,
        },
        "nfsMounts": [
            {
                "server": NFS_IP,
                "path": NFS_PATH,
                "mountPoint": NFS_MOUNT,
            }
        ],
    }]

print("uploading code files to GCS")

if NFS_ENABLE == False:
    job_spec = job_spec_default
else:
    job_spec = job_spec_nfs


code_upload_cmd = f"gsutil cp -r * {BUCKET_URI}/code".format(BUCKET_URI)
code_upload_process = subprocess.Popen(code_upload_cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
code_upload_process.wait()

print(f"code path {CODE_INPUT_DIR}".format(CODE_INPUT_DIR))

code_upload_returncode = code_upload_process.returncode
if(code_upload_returncode == 0):
    print("code files uploaded")
else:
    print("fail to uplaod code files")

@component(
    base_image="google/cloud-sdk",  # Use a different base image.
)
def image_build(
    project_id: str,
    region: str,
    source_code_path: str,
    image_uri: str
) -> NamedTuple('Outputs', [('docker_repo_uri', str),('project_id', str)]):
    import subprocess
    project_id = project_id
    location = region
    code_path = f"{source_code_path}"
    api_enable_cmd = "gcloud services enable artifactregistry.googleapis.com"
    print("enable artifact registry API")
    api_enable_process = subprocess.Popen(api_enable_cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    api_enable_process.wait()
    print("starting cloud build job")
    image_uri = image_uri
    build_step = f"""steps:
- name: 'gcr.io/cloud-builders/docker'
  args: [ 'build', '-f', 'Dockerfile_kohya', '-t', '{image_uri}', '.' ]
- name: 'gcr.io/cloud-builders/docker'
  args: ['push', '{image_uri}']
options:
  machineType: 'N1_HIGHCPU_8'
  diskSizeGb: '200'"""
    build_file = open(f"{code_path}/cloud-build-config.yaml", "wt")
    build_file.write(build_step)
    build_file.close()
    print(f"write build file to {code_path}")
    build_cmd = f"cd {code_path} && gcloud config set project {project_id} && gcloud builds submit --config cloud-build-config.yaml ."
    build_process = subprocess.Popen(build_cmd, shell=True, stdout=None, stderr=None)
    build_process.wait()
    build_returncode = build_process.returncode
    if(build_returncode == 0):
        print(f"cloud build job sucessed")
        print(f"docker image push to {image_uri}")
        return (image_uri, project_id)
    else:
        print(f"cloud build job failed")

# Define the workflow of the pipeline.
@kfp.dsl.pipeline(
    name="sd-model-training-pipeline",
    pipeline_root=PIPELINE_ROOT)
def pipeline(build_image : bool,
            ):
    from datetime import datetime
    current = datetime.now()
    current_str = current.strftime("%Y-%m-%d-%H-%M")
    with Condition(build_image == "True", "image_build_enable"):
        preprocess_task = image_build(project_id=PROJECT_ID, region=REGION, source_code_path=CODE_INPUT_DIR, image_uri=IMAGE_URI)
        training_job_run_op = CustomTrainingJobOp(
            project=preprocess_task.outputs["project_id"],
            network="projects/153260248093/global/networks/default",
            display_name=f"sd-model-training-{current_str}",
            worker_pool_specs=job_spec,
        )
    with Condition(build_image == "False", "image_build_disable"):
        training_job_run_op = CustomTrainingJobOp(
            project=PROJECT_ID,
            display_name=f"sd-model-training-{current_str}",
            network="projects/153260248093/global/networks/default",
            worker_pool_specs=job_spec,
        )
print("compiling pipeline")
current = datetime.now()
current_str = current.strftime("%Y-%m-%d-%H-%M")
package_path = f"{PIPELINE_NAME}-{current_str}.json".format(PIPELINE_NAME=PIPELINE_NAME, current_str=current_str)
compiler.Compiler().compile(
    pipeline_func=pipeline,
    package_path=package_path,
)

print(f"saving pipeline configuration file to {package_path}".format(package_path))

DISPLAY_NAME = f"{PIPELINE_NAME}-{current_str}".format(PIPELINE_NAME=PIPELINE_NAME, current_str=current_str)
job = aip.PipelineJob(
    display_name=DISPLAY_NAME,
    template_path=package_path,
    pipeline_root=PIPELINE_ROOT,
    enable_caching=False,
    parameter_values={
            'build_image': BUILD_IMAGE
        }
)
job.run()
