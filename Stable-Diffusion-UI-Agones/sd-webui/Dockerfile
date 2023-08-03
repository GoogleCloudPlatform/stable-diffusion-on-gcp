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

FROM nvidia/cuda:11.8.0-runtime-ubuntu22.04
# FROM nvidia/cuda:11.8.0-devel-ubuntu22.04

RUN set -ex && \
    apt update && \
    apt install -y wget git python3 python3-venv python3-pip libglib2.0-0 pkg-config libcairo2-dev ffmpeg libsm6 libxext6 libtcmalloc-minimal4 && \
    rm -rf /var/lib/apt/lists/*

RUN python3 -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118 --prefer-binary
RUN python3 -m pip install git+https://github.com/TencentARC/GFPGAN.git@8d2447a2d918f8eba5a4a01463fd48e45126a379 --prefer-binary
RUN python3 -m pip install git+https://github.com/openai/CLIP.git@d50d76daa670286dd6cacf3bcd80b5e4823fc8e1 --prefer-binary
RUN python3 -m pip install git+https://github.com/mlfoundations/open_clip.git@bb6e834e9c70d9c27d0dc3ecedeebeaeb1ffad6b --prefer-binary
RUN python3 -m pip install xformers --prefer-binary
RUN python3 -m pip install pyngrok --prefer-binary
RUN git clone https://github.com/AUTOMATIC1111/stable-diffusion-webui.git
RUN git -C /stable-diffusion-webui checkout 89f9faa63388756314e8a1d96cf86bf5e0663045
RUN git clone https://github.com/Stability-AI/stablediffusion.git /stable-diffusion-webui/repositories/stable-diffusion-stability-ai
RUN git -C /stable-diffusion-webui/repositories/stable-diffusion-stability-ai checkout cf1d67a6fd5ea1aa600c4df58e5b47da45f6bdbf
RUN git clone https://github.com/CompVis/taming-transformers.git /stable-diffusion-webui/repositories/taming-transformers
RUN git -C /stable-diffusion-webui/repositories/taming-transformers checkout 24268930bf1dce879235a7fddd0b2355b84d7ea6
RUN git clone https://github.com/crowsonkb/k-diffusion.git /stable-diffusion-webui/repositories/k-diffusion
RUN git -C /stable-diffusion-webui/repositories/k-diffusion checkout c9fe758757e022f05ca5a53fa8fac28889e4f1cf
RUN git clone https://github.com/sczhou/CodeFormer.git /stable-diffusion-webui/repositories/CodeFormer
RUN git -C /stable-diffusion-webui/repositories/CodeFormer checkout c5b4593074ba6214284d6acd5f1719b6c5d739af
RUN git clone https://github.com/salesforce/BLIP.git /stable-diffusion-webui/repositories/BLIP
RUN git -C /stable-diffusion-webui/repositories/BLIP checkout 48211a1594f1321b00f14c9f7a5b4813144b2fb9
RUN python3 -m pip install -r /stable-diffusion-webui/repositories/CodeFormer/requirements.txt --prefer-binary
RUN python3 -m pip install -r /stable-diffusion-webui/requirements_versions.txt --prefer-binary
RUN python3 -m pip install sqlalchemy --prefer-binary

RUN set -ex && cd stable-diffusion-webui \
    && git clone https://github.com/kohya-ss/sd-webui-additional-networks.git extensions/sd-webui-additional-networks \
    && git clone https://github.com/hnmr293/sd-webui-cutoff.git extensions/sd-webui-cutoff \
    && git clone https://github.com/toriato/stable-diffusion-webui-wd14-tagger.git extensions/stable-diffusion-webui-wd14-tagger \
    && git clone https://github.com/DominikDoom/a1111-sd-webui-tagcomplete.git extensions/a1111-sd-webui-tagcomplete \
    && git clone https://github.com/Mikubill/sd-webui-controlnet.git extensions/sd-webui-controlnet \
    && git clone https://github.com/zanllp/sd-webui-infinite-image-browsing.git extensions/sd-webui-infinite-image-browsing \
    && git -C /stable-diffusion-webui/extensions/sd-webui-infinite-image-browsing checkout 4720b15126c3ee05e97d50108050d1178e50639b \
    && git clone https://github.com/aria1th/Hypernetwork-MonkeyPatch-Extension.git extensions/Hypernetwork-MonkeyPatch-Extension \
    && git clone https://github.com/butaixianran/Stable-Diffusion-Webui-Civitai-Helper.git extensions/Stable-Diffusion-Webui-Civitai-Helper \
    && git clone https://github.com/ilian6806/stable-diffusion-webui-state.git extensions/stable-diffusion-webui-state \
    && git clone https://github.com/vladmandic/sd-extension-system-info extensions/sd-extension-system-info \
    && git clone https://github.com/ArtVentureX/sd-webui-agent-scheduler.git extensions/agent-scheduler
    # && git clone https://github.com/continue-revolution/sd-webui-segment-anything extensions/sd-webui-segment-anything

RUN python3 -m pip install -r /stable-diffusion-webui/extensions/sd-webui-controlnet/requirements.txt --prefer-binary
# RUN python3 -m pip install -r /stable-diffusion-webui/extensions/sd-webui-segment-anything/requirements.txt --prefer-binary

ENV SAFETENSORS_FAST_GPU=1
ENV LD_PRELOAD="/usr/lib/x86_64-linux-gnu/libtcmalloc_minimal.so.4"

EXPOSE 7860

COPY extensions/ /stable-diffusion-webui/extensions/
COPY user-watch.py /stable-diffusion-webui/user-watch.py
COPY start.sh /stable-diffusion-webui/start.sh
COPY *.json /stable-diffusion-webui/

WORKDIR /stable-diffusion-webui/
CMD ["python3", "webui.py", "--listen", "--opt-sdp-attention", "--enable-insecure-extension-access", "--api"]
