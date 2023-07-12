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

import subprocess
import os
import argparse
import re
import torch
from safetensors.torch import save_file

def main(args):
    
    subprocess.run("accelerate config default", shell=True)
    subprocess.run("cat /root/.cache/huggingface/accelerate/default_config.yaml", shell=True)

    METHOD = args.method
    NUM_CPU_THREADS = int(args.num_cpu_threads)
    MODEL_NAME= args.model_name #"runwayml/stable-diffusion-v1-5"
    INSTANCE_DIR= args.input_storage
    METADATA_DIR = args.metadata_storage
    OUTPUT_DIR= args.output_storage
    DISPLAY_NAME = args.display_name
    RESOLUTION = args.resolution
    MAX_EPOCHS = int(args.max_train_epochs)
    LR = float(args.lr)
    UNET_LR = float(args.unet_lr)
    TEXT_ENCODER_LR = float(args.text_encoder_lr)
    LR_SCHEDULER = args.lr_scheduler
    NETWORK_DIM = int(args.network_dim)
    NETWORK_ALPHA = int(args.network_alpha)
    BATCH_SIZE = int(args.batch_size)
    SAVE_N_EPOCHS = int(args.save_every_n_epochs)
    NETWORK_WEIGHTS = args.network_weights
    REG_DIR = args.reg_dir
    USE_8BIT_ADAM = bool(args.use_8bit_adam)
    USE_LION = bool(args.use_lion)
    NOISE_OFFSET = float(args.noise_offset)
    HPO = args.hpo

    if METHOD == "kohya_lora":
        os.chdir("/root/lora-scripts")
        # for complex commands, with many args, use string + `shell=True`:
        cmd_str = (f'accelerate launch --num_cpu_threads_per_process={NUM_CPU_THREADS} sd-scripts/train_network.py '
                   f'--enable_bucket '
                   f'--pretrained_model_name_or_path="{MODEL_NAME}" '
                   f'--train_data_dir="{INSTANCE_DIR}" '
                   f'--output_dir="{OUTPUT_DIR}" '
                   f'--logging_dir="{OUTPUT_DIR}/logs" '
                   f'--log_prefix="{DISPLAY_NAME}_logs" '
                   f'--resolution="{RESOLUTION}" '
                   f'--network_module="networks.lora" '
                   f'--max_train_epochs={MAX_EPOCHS} '
                   f'--learning_rate={LR} '
                   f'--unet_lr={UNET_LR} '
                   f'--text_encoder_lr={TEXT_ENCODER_LR} '
                   f'--lr_scheduler="{LR_SCHEDULER}" '
                   f'--lr_warmup_steps=0 '
                   f'--lr_scheduler_num_cycles=1 '
                   f'--network_dim={NETWORK_DIM} '
                   f'--network_alpha={NETWORK_ALPHA} '
                   f'--output_name="{DISPLAY_NAME}" '
                   f'--train_batch_size={BATCH_SIZE} '
                   f'--save_every_n_epochs={SAVE_N_EPOCHS} '
                   f'--mixed_precision="fp16" '
                   f'--save_precision="fp16" '
                   f'--seed="1337" '
                   f'--cache_latents '
                   f'--clip_skip=2 '
                   f'--prior_loss_weight=1 '
                   f'--max_token_length=225 '
                   f'--caption_extension=".txt" '
                   f'--save_model_as="safetensors" '
                   f'--min_bucket_reso=256 '
                   f'--max_bucket_reso=1024 '
                   f'--keep_tokens=0 '
                   f'--xformers --shuffle_caption '
                   f'--hpo="{HPO}"')
                                    
        if NETWORK_WEIGHTS:
            cmd_str += f' --network_weights="{NETWORK_WEIGHTS}"'
        if REG_DIR:
            cmd_str += f' --reg_data_dir="{REG_DIR}"'
        if USE_8BIT_ADAM == True:
            cmd_str += f' --use_8bit_adam'
        if USE_LION == True:
            cmd_str += f' --use_lion_optimizer'
        if NOISE_OFFSET:
            cmd_str += f' --noise_offset={NOISE_OFFSET}'
        if METADATA_DIR is not None:
            cmd_str += f' --in_json="{METADATA_DIR}"'
    
    # start training
    subprocess.run(cmd_str, shell=True)

    if bool(args.save_nfs) == True:
        nfs_path = args.nfs_mnt_dir

        if not os.path.exists(nfs_path):
            print("nfs not exist")
        else:
            if not os.path.exists(nfs_path + '/kohya'):
               os.mkdir(nfs_path + '/kohya')
               print(f"{nfs_path}/kohya has been created.")
            else:
               print(f"{nfs_path}/kohya already exists.")
            copy_cmd = f'cp {OUTPUT_DIR}/*.safetensors {nfs_path}/kohya'
            subprocess.run(copy_cmd, shell=True)
            subprocess.run(f'ls {nfs_path}/kohya', shell=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--method", type=str, default="kohya_lora", help="a tag")
    parser.add_argument("--num_cpu_threads", type=int, default=8, help="num of cpu threads per process")
    parser.add_argument("--model_name", type=str, default="runwayml/stable-diffusion-v1-5", help="bucket_name/model_folder")
    parser.add_argument("--input_storage", type=str,default="/root/dog_image_resize", help="/gcs/bucket_name/input_image_folder")
    parser.add_argument("--metadata_storage", type=str, default=None, help="metadata json path, for native training")
    parser.add_argument("--output_storage", type=str, default="/root/dog_output", help="/gcs/bucket_name/output_folder")
    parser.add_argument("--display_name", type=str, default="sks_dog", help="prompt")
    parser.add_argument("--resolution", type=str, default="512,512", help="resolution group")
    parser.add_argument("--max_train_epochs", type=int, default=10, help="max train epochs")
    parser.add_argument("--lr", type=float, default=1e-4, help="learning rate")
    parser.add_argument("--unet_lr", type=float, default=1e-4, help="unet learning rate")
    parser.add_argument("--text_encoder_lr", type=float, default=1e-5, help="text encoder learning rate")
    parser.add_argument("--lr_scheduler", type=str, default="cosine_with_restarts", help="")
    parser.add_argument("--network_dim", type=int, default=32, help="network dim 4~128")
    parser.add_argument("--network_alpha", type=int, default=32, help="often=network dim")
    parser.add_argument("--batch_size", type=int, default=1, help="batch size")
    parser.add_argument("--save_every_n_epochs", type=int, default=2, help="save every n epochs")
    parser.add_argument("--network_weights", type=str, default="", help="lora model path,/gcs/bucket_name/lora_model")
    parser.add_argument("--reg_dir", type=str, default="", help="regularization data path")
    parser.add_argument("--use_8bit_adam", type=bool, default=True, help="use 8bit adam optimizer")
    parser.add_argument("--use_lion", type=bool, default=False, help="lion optimizer")
    parser.add_argument("--noise_offset", type=int, default=0, help="0.1 if use")
    parser.add_argument("--save_nfs", type=bool, default=False, help="if save the model to file store")
    parser.add_argument("--save_nfs_only", type=bool, default=False, help="only copy file from gcs to filestore, no training")
    parser.add_argument("--nfs_mnt_dir", type=str, default="/mnt/nfs/model_repo", help="Filestore's mount directory")
    parser.add_argument("--hpo", type=str, default="n", help="if using hyper parameter tuning")
    
    args = parser.parse_args()
    print(args)
    if bool(args.save_nfs_only) == True:
        nfs_path = args.nfs_mnt_dir #"/mnt/nfs/model_repo"
        if not os.path.exists(nfs_path):
            print("nfs not exist")
        else:
            if not os.path.exists(nfs_path + '/kohya'):
               os.mkdir(nfs_path + '/kohya')
               print(f"{nfs_path}/kohya has been created.")
            else:
               print(f"{nfs_path}/kohya already exists.")
            copy_cmd = f'cp {args.output_storage}/*.safetensors {nfs_path}/kohya'
            subprocess.run(copy_cmd, shell=True)
            subprocess.run(f'ls {nfs_path}/kohya', shell=True)  
    else:
       main(args)
