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

def bin_to_safetensors(output_path):
    newDict = dict();
    checkpoint = torch.load(output_path + '/pytorch_lora_weights.bin');
    for idx, key in enumerate(checkpoint):
      newKey = re.sub('\.processor\.', '_', key);
      newKey = re.sub('mid_block\.', 'mid_block_', newKey);
      newKey = re.sub('_lora.up.', '.lora_up.', newKey);
      newKey = re.sub('_lora.down.', '.lora_down.', newKey);
      newKey = re.sub('\.(\d+)\.', '_\\1_', newKey);
      newKey = re.sub('to_out', 'to_out_0', newKey);
      newKey = 'lora_unet_'+newKey;

      newDict[newKey] = checkpoint[key];

    newLoraName = 'pytorch_lora_weights.safetensors';
    print("Saving " + newLoraName);
    save_file(newDict, output_path + '/' + newLoraName);

def main(args):
    
    subprocess.run("accelerate config default", shell=True)
    subprocess.run("cat /root/.cache/huggingface/accelerate/default_config.yaml", shell=True)

    METHOD = args.method
    MODEL_NAME= args.model_name #"runwayml/stable-diffusion-v1-5"
    INSTANCE_DIR= args.input_storage
    OUTPUT_DIR= args.output_storage
    PROMPT = args.prompt
    CLASS_PROMPT = args.class_prompt
    NUM_CLASS_IMAGES = int(args.num_class_images)
    STEPS = int(args.max_train_steps)
    TEXT_ENCODER = bool(args.text_encoder)
    SET_GRADS_TO_NONE = bool(args.set_grads_to_none)
    
    RESOLUTION = int(args.resolution)
    BATCH_SIZE = int(args.batch_size)
    USE_8BIT = bool(args.use_8bit)
    LR = float(args.lr)
    GRADIENT_ACCU_STEPS = int(args.gradient_accumulation_steps)
    NUM_VALID_IMG = int(args.num_validation_images)
    VALID_PRMOP = args.validation_prompt
    

    # Note the constraint: raise error: (args.train_text_encoder and args.gradient_accumulation_steps > 1 and accelerator.num_processes > 1)
    
    if METHOD == "diffuser_dreambooth":
        os.chdir("/root/diffusers/examples/dreambooth")
        # for complex commands, with many args, use string + `shell=True`:
        cmd_str = (f'accelerate launch train_dreambooth.py '
                   f'--pretrained_model_name_or_path="{MODEL_NAME}" '
                   f'--instance_data_dir="{INSTANCE_DIR}" '
                   f'--output_dir="{OUTPUT_DIR}" '
                   f'--instance_prompt="{PROMPT}" '
                   f'--class_data_dir="{OUTPUT_DIR}/class_data" '
                   f'--with_prior_preservation --prior_loss_weight=1.0 '
                   f'--class_prompt="{CLASS_PROMPT}" '
                   f'--resolution={RESOLUTION} '
                   f'--train_batch_size={BATCH_SIZE} '                   
                   f'--gradient_checkpointing '
                   f'--gradient_accumulation_steps={GRADIENT_ACCU_STEPS} '
                   f'--mixed_precision="fp16" '
                   f'--learning_rate={LR} '
                   f'--lr_scheduler="constant" '
                   f'--lr_warmup_steps=0 '
                   f'--num_class_images={NUM_CLASS_IMAGES} '
                   f'--enable_xformers_memory_efficient_attention '
                   f'--max_train_steps={STEPS}')
        
        if TEXT_ENCODER == True:
            cmd_str += f' --train_text_encoder'
        if SET_GRADS_TO_NONE == True:
            cmd_str += f' --set_grads_to_none'
        if USE_8BIT == True:
            cmd_str += f' --use_8bit_adam'
        
    elif METHOD == "diffuser_dreambooth_lora":
        os.chdir("/root/diffusers/examples/dreambooth")
        # for complex commands, with many args, use string + `shell=True`:
        cmd_str = (f'accelerate launch train_dreambooth_lora.py '
                   f'--pretrained_model_name_or_path="{MODEL_NAME}" '
                   f'--instance_data_dir="{INSTANCE_DIR}" '
                   f'--output_dir="{OUTPUT_DIR}" '
                   f'--instance_prompt="{PROMPT}" '
                   f'--resolution={RESOLUTION} '
                   f'--train_batch_size={BATCH_SIZE} '
                   f'--mixed_precision="fp16" '
                   f'--gradient_accumulation_steps={GRADIENT_ACCU_STEPS} '
                   f'--learning_rate={LR} '
                   f'--lr_scheduler="constant" '
                   f'--lr_warmup_steps=0 '
                   f'--max_train_steps={STEPS}')
    
        if USE_8BIT == True:
            cmd_str += f' --use_8bit_adam'

    elif METHOD == "diffuser_text_to_image":
        os.chdir("/root/diffusers/examples/text_to_image")
        cmd_str = (f'accelerate launch --mixed_precision="fp16" train_text_to_image.py '
                   f'--pretrained_model_name_or_path="{MODEL_NAME}" '
                   f'--train_data_dir="{INSTANCE_DIR}" '
                   f'--use_ema '
                   f'--resolution={RESOLUTION} --center_crop --random_flip '
                   f'--mixed_precision="fp16" '
                   f'--train_batch_size={BATCH_SIZE} '
                   f'--gradient_accumulation_steps={GRADIENT_ACCU_STEPS} '
                   f'--gradient_checkpointing '
                   f'--max_train_steps={STEPS} '
                   f'--learning_rate={LR} '
                   f'--max_grad_norm=1 '
                   f'--lr_scheduler="constant" '
                   f'--lr_warmup_steps=0 '
                   f'--enable_xformers_memory_efficient_attention '
                   f'--output_dir="{OUTPUT_DIR}"')

        if USE_8BIT == True:
            cmd_str += f' --use_8bit_adam'

    elif METHOD == "diffuser_text_to_image_lora":
        os.chdir("/root/diffusers/examples/text_to_image")
        cmd_str = (f'accelerate launch --mixed_precision="fp16" train_text_to_image_lora.py '
                   f'--pretrained_model_name_or_path="{MODEL_NAME}" '
                   f'--train_data_dir="{INSTANCE_DIR}" '
                   f'--resolution={RESOLUTION} --center_crop --random_flip '
                   f'--mixed_precision="fp16" '
                   f'--train_batch_size={BATCH_SIZE} '
                   f'--gradient_accumulation_steps={GRADIENT_ACCU_STEPS} '
                   f'--gradient_checkpointing '
                   f'--max_train_steps={STEPS} '
                   f'--learning_rate={LR} '
                   f'--max_grad_norm=1 '
                   f'--lr_scheduler="constant" --lr_warmup_steps=0 '
                   f'--seed=42 '
                   f'--num_validation_images={NUM_VALID_IMG} '
                   f'--validation_prompt="{VALID_PRMOP}" '
                   f'--output_dir="{OUTPUT_DIR}"')
        
    elif METHOD == "peft_lora":
        os.chdir("/root/peft/examples/lora_dreambooth")
                
        #create class data diretory
        if not os.path.exists(OUTPUT_DIR):
            os.mkdir(OUTPUT_DIR)
            print(f"{OUTPUT_DIR} has been created.")
        else:
            print(f"{OUTPUT_DIR} already exists.")
            
        class_directory = OUTPUT_DIR + '/class_data'
        if not os.path.exists(class_directory):
            os.mkdir(class_directory)
            print(f"{class_directory} has been created.")
        else:
            print(f"{class_directory} already exists.")

        # for complex commands, with many args, use string + `shell=True`:
        cmd_str = (f'accelerate launch train_dreambooth.py '
                   f'--pretrained_model_name_or_path="{MODEL_NAME}" '
                   f'--instance_data_dir="{INSTANCE_DIR}" '
                   f'--output_dir="{OUTPUT_DIR}" '
                   f'--with_prior_preservation '
                   f'--prior_loss_weight=1 '
                   f'--num_class_images={NUM_CLASS_IMAGES} '
                   f'--class_prompt="{CLASS_PROMPT}" '
                   f'--class_data_dir="{OUTPUT_DIR}/class_data" '
                   f'--instance_prompt="{PROMPT}" '
                   f'--use_lora '
                   f'--lora_r=4 '
                   f'--lora_alpha=4 '
                   f'--lora_bias=none '
                   f'--lora_dropout=0.0 '
                   f'--lora_text_encoder_r=4 '
                   f'--lora_text_encoder_alpha=4 '
                   f'--lora_text_encoder_bias=none '
                   f'--lora_text_encoder_dropout=0.0 '
                   f'--gradient_checkpointing '
                   f'--resolution=512 '
                   f'--train_batch_size=1 '
                   f'--use_8bit_adam '
                   f'--mixed_precision="fp16" '
                   f'--gradient_accumulation_steps=1 '
                   f'--learning_rate=1e-4 '
                   f'--lr_scheduler="constant" '
                   f'--lr_warmup_steps=0 '
                   f'--enable_xformers_memory_efficient_attention '
                   f'--max_train_steps={STEPS}')
        if TEXT_ENCODER == True:
            cmd_str += f' --train_text_encoder '


    
    # start training
    subprocess.run(cmd_str, shell=True)

    # convert to safetensors
    if (METHOD == "diffuser_dreambooth_lora") or (METHOD == "diffuser_text_to_image_lora"):
        bin_to_safetensors(args.output_storage)

    if (METHOD == "diffuser_dreambooth") or (METHOD == "diffuser_text_to_image"):
        subprocess.run(f'python3 /root/diffusers/scripts/convert_diffusers_to_original_stable_diffusion.py --model_path {OUTPUT_DIR} --checkpoint_path {OUTPUT_DIR}/dreambooth.safetensors --use_safetensors', shell=True)

    if bool(args.save_nfs) == True:
        nfs_path = args.nfs_mnt_dir

        if not os.path.exists(nfs_path):
            print("nfs not exist")
        else:
            if not os.path.exists(nfs_path + '/' + args.method):
               os.mkdir(nfs_path + '/' + args.method)
               print(f"{nfs_path}/{args.method} has been created.")
            else:
               print(f"{nfs_path}/{args.method} already exists.")
            copy_cmd = f'cp {OUTPUT_DIR}/*.safetensors {nfs_path}/{args.method}'
            subprocess.run(copy_cmd, shell=True)
            subprocess.run(f'ls {nfs_path}/{args.method}', shell=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--method", type=str, default="diffuser_dreambooth_lora", help="dreambooth/dreambooth_lora/peft_lora")
    parser.add_argument("--model_name", type=str, default="runwayml/stable-diffusion-v1-5", help="bucket_name/model_folder")
    parser.add_argument("--input_storage", type=str,default="abc", help="/gcs/bucket_name/input_image_folder")
    parser.add_argument("--output_storage", type=str, default="abc",help="/gcs/bucket_name/output_folder")
    parser.add_argument("--prompt", type=str, default="a photo of sks dog",help="instance prompt")
    parser.add_argument("--class_prompt", type=str, required=False,default="a photo of dog",help="instance prompt")
    parser.add_argument("--max_train_steps", type=int, default=400,help="training steps")
    parser.add_argument("--text_encoder", type=bool, default=True,help="train text encoder")
    parser.add_argument("--set_grads_to_none", type=bool, default=False,help="set grads to none if CUDA memory if very low <16GB")
    parser.add_argument("--num_class_images", type=int, default=50, help="generate image number")
    
    parser.add_argument("--resolution", type=int, default=512, help="resize input image resolution to")
    parser.add_argument("--batch_size", type=int, default=1, help="training batch size")
    parser.add_argument("--use_8bit", type=bool, default=True, help="use 8bit adam optimizer")
    parser.add_argument("--lr", type=float, default=1e-4, help="lora=1e-4,others=1e-5")
    parser.add_argument("--gradient_accumulation_steps", type=int, default=1, help="gradient accumulation steps")
    parser.add_argument("--num_validation_images", type=int, default=4, help="num_validation_images, text_to_image_lora")
    parser.add_argument("--validation_prompt", type=str, default="a photo of sks dog in the forest", help="validation prompt")
    parser.add_argument("--save_nfs", type=bool, default=False, help="if save the model to file store")
    parser.add_argument("--save_nfs_only", type=bool, default=False, help="only copy file from gcs to filestore, no training")
    parser.add_argument("--nfs_mnt_dir", type=str, default="/mnt/nfs/model_repo", help="Filestore's mount directory")

    args = parser.parse_args()
    print(args)
    if bool(args.save_nfs_only) == True:
        nfs_path = args.nfs_mnt_dir
        if not os.path.exists(nfs_path):
            print("nfs not exist")
        else:
            if not os.path.exists(nfs_path + '/' + args.method):
               os.mkdir(nfs_path + '/' + args.method)
               print(f"{nfs_path}/{args.method} has been created.")
            else:
               print(f"{nfs_path}/{args.method} already exists.")
            copy_cmd = f'cp {args.output_storage}/*.safetensors {nfs_path}/{args.method}'
            subprocess.run(copy_cmd, shell=True)
            subprocess.run(f'ls {nfs_path}/{args.method}', shell=True) 
    else:
       main(args)
