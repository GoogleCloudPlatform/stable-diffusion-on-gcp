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
import json
import shutil
import requests
import time
import os
from pathlib import Path


sdk_http_port = os.environ['AGONES_SDK_HTTP_PORT']
mount_dir = '/sd_dir'

if os.path.isdir('/stable-diffusion-webui/models'):
    shutil.rmtree('/stable-diffusion-webui/models')

os.symlink(os.path.join(mount_dir, 'models'), '/stable-diffusion-webui/models', target_is_directory = True)

if os.path.isdir('/stable-diffusion-webui/embeddings'):
    shutil.rmtree('/stable-diffusion-webui/embeddings')

os.symlink(os.path.join(mount_dir, 'embeddings'), '/stable-diffusion-webui/embeddings', target_is_directory = True)

url = 'http://localhost:' + sdk_http_port + '/watch/gameserver'

time.sleep(30)

r = requests.get(url, stream=True)

if r.encoding is None:
    r.encoding = 'utf-8'

for line in r.iter_lines(decode_unicode=True):
    if line: 
        response = json.loads(line)
        if "user" in response['result']['object_meta']['labels']:
            userid = response['result']['object_meta']['labels']['user']
            print(userid)
            # setup folders here
            if os.path.isdir('/stable-diffusion-webui/outputs'):
                shutil.rmtree('/stable-diffusion-webui/outputs')
            # if os.path.isdir('/stable-diffusion-webui/models'):
            #     shutil.rmtree('/stable-diffusion-webui/models')

            Path(os.path.join(mount_dir, userid, 'outputs')).mkdir(parents=True, exist_ok=True)
            Path(os.path.join(mount_dir, userid, 'inputs')).mkdir(parents=True, exist_ok=True)

            os.symlink(os.path.join(mount_dir, userid, 'outputs'), '/stable-diffusion-webui/outputs', target_is_directory = True)
            os.symlink(os.path.join(mount_dir, userid, 'inputs'), '/stable-diffusion-webui/inputs', target_is_directory = True)
            # os.symlink(os.path.join(mount_dir, 'models'), '/stable-diffusion-webui/models', target_is_directory = True)
            
            # webui config files
            # Path(os.path.join(mount_dir, userid, 'ui-configs')).mkdir(parents=True, exist_ok=True)
            
            # config_files_to_link = ['ui-config.json', 'config.json']
            
            # for file in config_files_to_link:
            #     file_origin = os.path.join('/stable-diffusion-webui', file)
            #     file_dest = os.path.join(mount_dir, userid, 'ui-configs', file)
            #     if os.path.isfile(file_origin) and not os.path.isfile(file_dest):
            #         shutil.copy2(file_origin, file_dest)
            #     if os.path.isfile(file_dest):
            #         os.remove(file_origin)
            #         os.symlink(file_dest, file_origin, target_is_directory = False)

            break