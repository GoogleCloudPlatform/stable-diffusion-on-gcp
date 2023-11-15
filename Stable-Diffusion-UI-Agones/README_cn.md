# Stable-Diffusion on Agones 实施指南

本指南为Stable-Diffusion-WebUI用户提供了简单的步骤，以使用 GCP GKE 服务启动Stable-Diffusion-WebUI部署，并使用 Filestore 作为模型和输出文件的共享存储。 为了方便多用户的Stable-Diffusion运行时管理，我们使用了 [Agones](https://agones.dev/site/) 作为运行时管理的控制平面，每个独立的Stable-Diffusion-WebUI都托管在一个独立的 POD 中，每个授权用户 将分配一个专用 POD。 用户只需按照步骤运行Stable-Diffusion-WebUI即可。

* [简介](#简介)
* [操作方法](#操作方法)

## 介绍
本项目使用[Stable-Diffusion-WebUI](https://github.com/AUTOMATIC1111/stable-diffusion-webui)开源作为用户交互前端，客户只需准备Stable-Diffusion模型即可构建/通过容器部署Stable-Diffusion模型。 该项目使用Cloud Build来帮助您使用Stable-Diffusion模型快速构建 docker 镜像，然后您可以基于 docker 镜像进行部署。 为了提供多用户隔离的Stable-Diffusion运行时，使用 [Agones](https://agones.dev/site/) 作为运行时管理的控制平面，Agones 根据用户的资源需求管理和控制Stable-Diffusion运行时的生命周期。

## 架构
![sd-agones-arch](images/sd-agones-arch.png)

## 如何使用
您可以使用Cloud Shell作为运行时来执行以下步骤。

### 在你开始之前
1. 确保您有一个可用的 GCP 项目用于部署
2. 使用 [cloud shell](https://cloud.google.com/shell/docs/run-gcloud-commands) 启用所需的服务 API
```
gcloud services enable compute.googleapis.com artifactregistry.googleapis.com container.googleapis.com file.googleapis.com vpcaccess.googleapis.com redis.googleapis.com cloudscheduler.googleapis.com cloudfunctions.googleapis.com cloudbuild.googleapis.com
```
1. 在项目中移除以下organization policy的限制（如果有）
```
constraints/compute.vmExternalIpAccess
constraints/compute.requireShieldedVm  
constraints/cloudfunctions.allowedIngressSettings
constraints/iam.allowedPolicyMemberDomains(optional)
```

### 初始化环境变量

```
PROJECT_ID=<替换为你的项目ID>
GKE_CLUSTER_NAME=<替换为你的GKE集群名字>
REGION=<替换为你的区域>
VPC_NETWORK=<替换为你的VPC网络名字>
VPC_SUBNETWORK=<替换为你的VPC子网名字>
BUILD_REGIST=<替换为你的Artifact Registry代码仓库名字>
FILESTORE_NAME=<替换为你的Filestore实例名字>
FILESTORE_ZONE=<替换为你的Filestore实例所在的可用区>
FILESHARE_NAME=<替换为你的Fileshare共享盘路径的名字>
```

### 创建 GKE 集群
使用Cloud Shell执行以下步骤。 本指南使用 T4 GPU 节点作为 VM 主机，根据您的选择，您可以将节点类型更改为 [其他 GPU 实例类型](https://cloud.google.com/compute/docs/gpus)。
在本指南中，我们还为models/outputs共享启用了 [Filestore CSI 驱动程序](https://cloud.google.com/kubernetes-engine/docs/how-to/persistent-volumes/filestore-csi-driver)。
如果你准备使用的是 [GcsFuse CSI 驱动程序](https://cloud.google.com/kubernetes-engine/docs/how-to/persistent-volumes/cloud-storage-fuse-csi-driver)，请遵循GcsFuse相关的注解。
```

gcloud beta container --project ${PROJECT_ID} clusters create ${GKE_CLUSTER_NAME} --region ${REGION} \
    --no-enable-basic-auth --release-channel "None" \
    --machine-type "e2-standard-2" \
    --image-type "COS_CONTAINERD" --disk-type "pd-balanced" --disk-size "100" \
    --metadata disable-legacy-endpoints=true --scopes "https://www.googleapis.com/auth/cloud-platform" \
    --num-nodes "1" --logging=SYSTEM,WORKLOAD --monitoring=SYSTEM \
    # uncomment below for private cluster 
    # --enable-private-nodes --master-ipv4-cidr "172.16.0.0/28" --enable-master-global-access \
    --enable-ip-alias \
    --network "projects/${PROJECT_ID}/global/networks/${VPC_NETWORK}" \
    --subnetwork "projects/${PROJECT_ID}/regions/${REGION}/subnetworks/${VPC_SUBNETWORK}" \
    --no-enable-intra-node-visibility --default-max-pods-per-node "110" --no-enable-master-authorized-networks \
    --addons HorizontalPodAutoscaling,HttpLoadBalancing,GcePersistentDiskCsiDriver,GcpFilestoreCsiDriver \
    --autoscaling-profile optimize-utilization

gcloud beta container --project ${PROJECT_ID} node-pools create "gpu-pool" \
	--cluster ${GKE_CLUSTER_NAME} \
	--region ${REGION} \
	--machine-type "custom-4-32768-ext" \
	--accelerator "type=nvidia-tesla-t4,count=1" \
	--image-type "COS_CONTAINERD" \
	--disk-type "pd-balanced" \
	--disk-size "100" \
	--metadata disable-legacy-endpoints=true \
	--scopes "https://www.googleapis.com/auth/devstorage.read_only","https://www.googleapis.com/auth/logging.write","https://www.googleapis.com/auth/monitoring","https://www.googleapis.com/auth/servicecontrol","https://www.googleapis.com/auth/service.management.readonly","https://www.googleapis.com/auth/trace.append" \
	--num-nodes "1" \
	--enable-autoscaling \
	--total-min-nodes "0" --total-max-nodes "3" \
	--location-policy "ANY" --enable-autoupgrade --enable-autorepair --max-surge-upgrade 1 --max-unavailable-upgrade 0
```
**注意：如果你要使用的是GcsFuse CSI，则用下列指令来创建集群**
```
# 创建 GKE 集群同时开启 workload identity
gcloud beta container --project ${PROJECT_ID} clusters create ${GKE_CLUSTER_NAME} --region ${REGION} \
    --no-enable-basic-auth --release-channel "regular" \
    --machine-type "e2-medium" \
    --image-type "COS_CONTAINERD" --disk-type "pd-balanced" --disk-size "100" \
    --metadata disable-legacy-endpoints=true --scopes "https://www.googleapis.com/auth/devstorage.read_only","https://www.googleapis.com/auth/logging.write","https://www.googleapis.com/auth/monitoring","https://www.googleapis.com/auth/servicecontrol","https://www.googleapis.com/auth/service.management.readonly","https://www.googleapis.com/auth/trace.append" \
    --num-nodes "1" --logging=SYSTEM,WORKLOAD --monitoring=SYSTEM \
    # uncomment below for private cluster 
    # --enable-private-nodes --master-ipv4-cidr "172.16.0.0/28" --enable-master-global-access \
    --enable-ip-alias \
    --network "projects/${PROJECT_ID}/global/networks/${VPC_NETWORK}" \
    --subnetwork "projects/${PROJECT_ID}/regions/${REGION}/subnetworks/${VPC_SUBNETWORK}" \
    --no-enable-intra-node-visibility --default-max-pods-per-node "110" --enable-autoscaling \
    --total-min-nodes "0" --total-max-nodes "3" --location-policy "ANY" --security-posture=standard \
    --workload-vulnerability-scanning=standard --no-enable-master-authorized-networks \
    --addons HorizontalPodAutoscaling,HttpLoadBalancing,GcePersistentDiskCsiDriver,GcpFilestoreCsiDriver \
    --enable-autoupgrade --enable-autorepair --max-surge-upgrade 1 --max-unavailable-upgrade 0 --binauthz-evaluation-mode=DISABLED \
    --enable-managed-prometheus --workload-pool "${PROJECT_ID}.svc.id.goog" --enable-shielded-nodes

# 给现有集群开启 workload identity,

gcloud container clusters update ${GKE_CLUSTER_NAME} \
    --region=${REGION} \
    --workload-pool="${PROJECT_ID}.svc.id.goog"

# 给现有集群开启 GcsFuseCsiDriver

gcloud container clusters update ${GKE_CLUSTER_NAME} \
    --update-addons GcsFuseCsiDriver=ENABLED \
    --region=${REGION}

# GPU node pool 建议分配 200GB 磁盘大小, 因为 GcsFuse sidecar 默认使用 50GiB 作为缓存空间,
# refer to https://cloud.google.com/kubernetes-engine/docs/how-to/persistent-volumes/cloud-storage-fuse-csi-driver#sidecar-container

gcloud beta container --project ${PROJECT_ID} node-pools create "gpu-pool" \
	--cluster ${GKE_CLUSTER_NAME} \
	--region ${REGION} \
	--machine-type "custom-4-32768-ext" \
	--accelerator "type=nvidia-tesla-t4,count=1" \
	--image-type "COS_CONTAINERD" \
	--disk-type "pd-balanced" \
	--disk-size "200" \
	--metadata disable-legacy-endpoints=true \
	--scopes "https://www.googleapis.com/auth/devstorage.read_only","https://www.googleapis.com/auth/logging.write","https://www.googleapis.com/auth/monitoring","https://www.googleapis.com/auth/servicecontrol","https://www.googleapis.com/auth/service.management.readonly","https://www.googleapis.com/auth/trace.append" \
	--num-nodes "1" \
	--enable-autoscaling \
	--total-min-nodes "0" --total-max-nodes "3" \
	--location-policy "ANY" --enable-autoupgrade --enable-autorepair --max-surge-upgrade 1 --max-unavailable-upgrade 0
```

### 针对Agones的防火墙配置
1. 如创建的是公有集群, 放行 0.0.0.0/0
2. 如创建的是私有集群, 可以考虑放行所有的内网网段(10.0.0.0/8, 172.16.0.0/16, 192.168.0.0/24)。准确来说需要放行的是所有pod需要使用到的内网网段, 但放行所有内网网段会更容易一些
3. TCP 端口 443/8080/8081 与 7000-8000 以及 UDP 端口 7000-8000
4. 目标设置为 GKE 节点的网络标签, e.g. gke-gke-01-7267dc32-node, 网络标签可以在 VM console里找到

**注意: 如果创建的是私有集群，你需要为GKE集群所在的子网创建一个Cloud NAT，因为sd-webui需要访问互联网以自动下载缺失的模型文件**

```
gcloud compute firewall-rules create allow-agones \
	--direction=INGRESS --priority=1000 --network=${VPC_NETWORK} --action=ALLOW \
	--rules=tcp:443,tcp:8080,tcp:8081,tcp:7000-8000,udp:7000-8000 \
	--source-ranges=0.0.0.0/0 \
	--target-tags=${GKE_NODE_NETWORK_TAG}
```

### 获取 GKE 集群的凭证
```
gcloud container clusters get-credentials ${GKE_CLUSTER_NAME} --region ${REGION}
```

### 安装显卡驱动
```
kubectl apply -f https://raw.githubusercontent.com/GoogleCloudPlatform/container-engine-accelerators/master/nvidia-driver-installer/cos/daemonset-preloaded.yaml
```
如果使用L4等最新的显卡，请执行以下指令安装更新的驱动
```
kubectl apply -f https://raw.githubusercontent.com/GoogleCloudPlatform/container-engine-accelerators/master/nvidia-driver-installer/cos/daemonset-preloaded-latest.yaml
```

### 创建Cloud Artifacts作为 Docker 镜像仓库
```

BUILD_REGIST=<将其替换为您首选的 Cloud Artifacts 镜像仓库名称>

gcloud artifacts repositories create ${BUILD_REGIST} --repository-format=docker \
--location=${REGION}

gcloud auth configure-docker ${REGION}-docker.pkg.dev
```
### 授予 GKE 集群 Cloud Artifacts 的读权限
GKE 集群默认使用compute engine的默认service account来访问 Artifacts registry.
更新以下命令中的变量 SERVICE_ACCOUNT_EMAIL 为你的默认 compute engine service account后执行
```
gcloud artifacts repositories add-iam-policy-binding ${BUILD_REGIST} \
    --location=${REGION} \
    --member=serviceAccount:SERVICE_ACCOUNT_EMAIL \
    --role="roles/artifactregistry.reader"
```
细节请参考，https://cloud.google.com/kubernetes-engine/docs/troubleshooting#permission_denied_error

### 构建Stable Diffusion容器镜像
使用提供的 Dockerfile 构建镜像，推送到 Cloud Artifacts 中的 repo

```
cd Stable-Diffusion-on-GCP/Stable-Diffusion-UI-Agones/sd-webui
docker build . -t ${REGION}-docker.pkg.dev/${PROJECT_ID}/${BUILD_REGIST}/sd-webui:0.1
docker push ${REGION}-docker.pkg.dev/${PROJECT_ID}/${BUILD_REGIST}/sd-webui:0.1

```

也可以用Cloud Build来构建
```
gcloud builds submit \
--machine-type=e2-highcpu-32 \
--disk-size=100 \
--region=us-central1 \
-t ${REGION}-docker.pkg.dev/${PROJECT_ID}/${BUILD_REGIST}/sd-webui:0.1
```

**注意：如果你使用的是GcsFuse CSI，就不需要创建Filestore**
### 创建Filestore共享存储
创建 Filestore 存储，为模型/输出/训练数据准备文件和文件夹
您应该准备一个 VM 来挂载(mount) 文件存储实例。

```
FILESTORE_NAME=<替换为文件存储实例名称>
FILESTORE_ZONE=<替换为文件存储实例区域>
FILESHARE_NAME=<替换为文件共享名称>


gcloud filestore instances create ${FILESTORE_NAME} --zone=${FILESTORE_ZONE} --tier=BASIC_HDD --file-share=name=${FILESHARE_NAME},capacity=1TB --network=name=${VPC_NETWORK}
e.g.
gcloud filestore instances create nfs-store --zone=us-central1-b --tier=BASIC_HDD --file-share=name="vol1",capacity=1TB --network=name=${VPC_NETWORK}

```
部署 PV 和 PVC 资源，将 nfs-server-ip 替换为之前在文件 nfs_pv.yaml 中创建的 nfs 实例的 ip 地址。
```
kubectl apply -f ./Stable-Diffusion-UI-Agones/agones/nfs_pv.yaml
kubectl apply -f ./Stable-Diffusion-UI-Agones/agones/nfs_pvc.yaml
```

**注意：在成功运行sd-webui的pod之前，你需要初始化Filestore share中的文件和目录** \
一个简单的做法是，
1. 在Filestore实例的相同子网中创建一个VM
2. 在VM上挂载 Filestore share，[参考](https://cloud.google.com/filestore/docs/mounting-fileshares)
```
sudo apt-get -y update && sudo apt-get install nfs-common -y
sudo mkdir -p /mnt/vol1
sudo mount -o rw,intr ${FILESTORE_IP}:/vol1 /mnt/vol1
```
3. 将A1111 的repo克隆下来, 复制目录 models/ & embeddings/ 到Filestore share下。这是因为我们在pod初始化的时候会执行一个脚本，脚本会创建到这两个目录的symlink以实现目录在多用户中共享，但这两个目录本身不是空的，因此mount的时候会被覆盖，因此需要提前准备好。
```
git clone https://github.com/AUTOMATIC1111/stable-diffusion-webui.git
cd stable-diffusion-webui
cp -rp models embeddings /mnt/vol1
```
4. 启动的时候让webui在启动中顺便初始化文件和目录 
```
docker run -it --gpus all -p7860:7860 -v /mnt/vol1/models/:/stable-diffusion-webui/models/ -v /mnt/vol1/embeddings/:/stable-diffusion-webui/embeddings/ ${REGION}-docker.pkg.dev/${PROJECT_ID}/${BUILD_REGIST}/sd-webui:0.1 /bin/bash
python3 webui.py --listen
```
执行完以上操作后，你的filestore share上应该已经有正确的文件和目录让sd-webui正常启动。

**注意：如果你使用的是Filestore CSI，则不需要创建Gcs相关的步骤**
### 创建 GcsFuse 使用的存储桶
执行该文档中的第一和第二步，[GcsFuse文档](https://github.com/GoogleCloudPlatform/gcs-fuse-csi-driver/blob/main/docs/authentication.md) 创建gcs bucket 以及 IAM. \
后续 update the bucket name variable in gcs_pv.yaml, and run
```
kubectl apply -f ./Stable-Diffusion-UI-Agones/agones/gcs_pv.yaml
kubectl apply -f ./Stable-Diffusion-UI-Agones/agones/gcs_pvc.yaml
```

### 安装Agones
在 default-pool 上安装 Agones Operator，default-pool 上会长期运行 Agones Operator 。
注意：为了快速启动，您可以使用已经安装了 helm 的 cloud shell。
```
helm repo add agones https://agones.dev/chart/stable
helm repo update
kubectl create namespace agones-system
cd Stable-Diffusion-on-GCP/Stable-Diffusion-UI-Agones
# Current agones setup require agones<=1.33.0
helm install sd-agones-release --namespace agones-system -f ./agones/values.yaml agones/agones --version 1.33.0
```

### 创建 Redis 缓存
创建一个redis缓存实例来承载访问信息。
```
gcloud redis instances create --project=${PROJECT_ID}  sd-agones-cache --tier=standard --size=1 --region=${REGION} --redis-version=redis_6_x --network=projects/${PROJECT_ID}/global/networks/${VPC_NETWORK} --connect-mode=DIRECT_PEERING
```

记录redis实例连接ip地址。
```
gcloud redis instances describe sd-agones-cache --region ${REGION} --format=json | jq .host
```

### 构建nginx代理镜像
使用提供的 Dockerfile 构建映像， 请将 gcp-stable-diffusion-build-deploy/Stable-Diffusion-UI-Agones/nginx/sd.lua 中的 ${REDIS_HOST} 替换为上一步记录的 ip 地址。

```
cd Stable-Diffusion-on-GCP/Stable-Diffusion-UI-Agones/nginx
REDIS_IP=$(gcloud redis instances describe sd-agones-cache --region ${REGION} --format=json 2>/dev/null | jq .host)
sed -i "s@\"\${REDIS_HOST}\"@${REDIS_IP}@g" sd.lua

docker build . -t ${REGION}-docker.pkg.dev/${PROJECT_ID}/${BUILD_REGIST}/sd-nginx:0.1
docker push ${REGION}-docker.pkg.dev/${PROJECT_ID}/${BUILD_REGIST}/sd-nginx:0.1
```
或者使用Cloud Build
```
gcloud builds submit \
--machine-type=e2-highcpu-32 \
--disk-size=100 \
--region=us-central1 \
-t ${REGION}-docker.pkg.dev/${PROJECT_ID}/${BUILD_REGIST}/sd-nginx:0.1
```


### 构建agones-sidecar镜像
使用提供的 Dockerfile 构建映像，推送到 Cloud Artifacts 中的 repo。该镜像为可选，目的是为了劫持sd-webui在启动完成之前返回的502，优化最终用户的体验。
```
cd Stable-Diffusion-on-GCP/Stable-Diffusion-UI-Agones/agones-sidecar
docker build . -t ${REGION}-docker.pkg.dev/${PROJECT_ID}/${BUILD_REGIST}/sd-agones-sidecar:0.1
docker push ${REGION}-docker.pkg.dev/${PROJECT_ID}/${BUILD_REGIST}/sd-agones-sidecar:0.1
```
或者使用Cloud Build.
```
gcloud builds submit \
--machine-type=e2-highcpu-32 \
--disk-size=100 \
--region=us-central1 \
-t ${REGION}-docker.pkg.dev/${PROJECT_ID}/${BUILD_REGIST}/sd-agones-sidecar:0.1
```

### 利用Agones部署Stable Diffusion WebUI
部署 stable-diffusion agone deployment，请将deployment.yaml和fleet yaml中的image URL替换为之前构建的容器镜像url。
```
cd Stable-Diffusion-on-GCP/Stable-Diffusion-UI-Agones/agones
sed -i "s@<REGION>@${REGION}@g" fleet_pvc.yaml
sed -i "s@<PROJECT_ID>/<BUILD_REGIST>@${PROJECT_ID}/${BUILD_REGIST}@g" fleet_pvc.yaml
cd -

cd Stable-Diffusion-on-GCP/Stable-Diffusion-UI-Agones/nginx
sed -i "s@<REGION>@${REGION}@g" deployment.yaml
sed -i "s@<PROJECT_ID>/<BUILD_REGIST>@${PROJECT_ID}/${BUILD_REGIST}@g" deployment.yaml
cd -

kubectl apply -f Stable-Diffusion-on-GCP/Stable-Diffusion-UI-Agones/nginx/deployment.yaml
kubectl apply -f Stable-Diffusion-on-GCP/Stable-Diffusion-UI-Agones/agones/fleet_pvc.yaml
kubectl apply -f Stable-Diffusion-on-GCP/Stable-Diffusion-UI-Agones/agones/fleet_autoscale.yaml
```

### 部署 stable-diffusion agones deployment(GcsFuse CSI)
要部署 stable-diffusion agones deployment, 需要先替换 deployment.yaml和fleet_xxx*.yaml中前面步骤中构建好的的image URL(nginx, optional agones-sidecar and sd-webui)。 \
部署前请先配置好 Kubernetes service account 与 IAM 之间的绑定关系，可以参考该文档中的第四步 [GcsFuse文档](https://github.com/GoogleCloudPlatform/gcs-fuse-csi-driver/blob/main/docs/authentication.md). \
我们需要复用现有的 Agones Kubernetes service account，也就是agones-sdk而不是创建新的，因为我们已经在用agones-sdk来创建agones fleets。
```
CLUSTER_PROJECT_ID=<replace it with the cluster project id>
GCS_BUCKET_PROJECT_ID=<replace it with the bucket project id>
GCP_SA_NAME=<replace it with the IAM service account to access the GCS bucket>

K8S_NAMESPACE=default
K8S_SA_NAME=agones-sdk

gcloud iam service-accounts add-iam-policy-binding ${GCP_SA_NAME}@${GCS_BUCKET_PROJECT_ID}.iam.gserviceaccount.com \
    --role roles/iam.workloadIdentityUser \
    --member "serviceAccount:${CLUSTER_PROJECT_ID}.svc.id.goog[${K8S_NAMESPACE}/${K8S_SA_NAME}]"

kubectl annotate serviceaccount ${K8S_SA_NAME} \
    --namespace ${K8S_NAMESPACE} \
    iam.gke.io/gcp-service-account=${GCP_SA_NAME}@${GCS_BUCKET_PROJECT_ID}.iam.gserviceaccount.com
```
后续的步骤跟Filestore版本的一样，需注意对应的文件改为fleet_gcs.yaml。
```
cd Stable-Diffusion-on-GCP/Stable-Diffusion-UI-Agones/agones
sed -i "s@<REGION>@${REGION}@g" fleet_gcs.yaml
sed -i "s@<PROJECT_ID>/<BUILD_REGIST>@${PROJECT_ID}/${BUILD_REGIST}@g" fleet_gcs.yaml
cd -

cd Stable-Diffusion-on-GCP/Stable-Diffusion-UI-Agones/nginx
sed -i "s@<REGION>@${REGION}@g" deployment.yaml
sed -i "s@<PROJECT_ID>/<BUILD_REGIST>@${PROJECT_ID}/${BUILD_REGIST}@g" deployment.yaml
cd -

kubectl apply -f Stable-Diffusion-on-GCP/Stable-Diffusion-UI-Agones/nginx/deployment.yaml
kubectl apply -f Stable-Diffusion-on-GCP/Stable-Diffusion-UI-Agones/agones/fleet_gcs.yaml
kubectl apply -f Stable-Diffusion-on-GCP/Stable-Diffusion-UI-Agones/agones/fleet_autoscale.yaml
```


### 准备 Cloud Function Serverless VPC 访问
创建无服务器 VPC 访问连接器，Cloud Function使用它来连接私有连接端点。
```
gcloud compute networks vpc-access connectors create sd-agones-connector --network ${VPC_NETWORK} --region ${REGION} --range 192.168.240.16/28
```

### 部署 Cloud Function Cruiser 程序
此 Cloud Function 作为 Cruiser 监控空闲用户，默认情况下当用户空闲 15 分钟时，stable-diffusion 运行时将被收集回来。 请将${REDIS_HOST}替换为上一步记录的redis实例ip地址。 要自定义空闲超时默认设置，请通过设置变量 TIME_INTERVAL 来覆盖设置。
```
cd Stable-Diffusion-on-GCP/Stable-Diffusion-UI-Agones/cloud-function
gcloud functions deploy redis_http --runtime python310 --trigger-http --allow-unauthenticated --region=${REGION} --vpc-connector=sd-agones-connector --egress-settings=private-ranges-only --set-env-vars=REDIS_HOST=${REDIS_HOST}
```
记录函数触发器 url。
```
gcloud functions describe redis_http --region us-central1 --format=json | jq .httpsTrigger.url
```
创建Cruiser调度程序。 请在上一步中将 ${FUNCTION_URL} 更改为 url。
```
gcloud scheduler jobs create http sd-agones-cruiser \
    --location=${REGION} \
    --schedule="*/5 * * * *" \
    --uri=${FUNCTION_URL}
```

### 部署 IAP（identity awared proxy身份感知代理）
分配隔离的Stable Diffusion运行时并提供用户访问身份验证功能，使用Google Cloud IAP 服务作为访问网关提供身份检查并将身份传递给Stable Diffusion后端。

配置 [OAuth consent screen](https://developers.google.com/workspace/guides/configure-oauth-consent) 和 [OAuth credentials](https://developers.google.com/workspace/guides/create-credentials#oauth-client-id)，最后配置 [identity aware proxy for backend serivce on GKE](https://cloud.google.com/iap/docs/enabling-kubernetes-howto#oauth-configure).

在 OAuth credentials 界面下创建 OAuth 2.0 Client IDs 后, 按下列格式更新 "Authorized redirect URIs"，将<>符号内的内容替换为对应的Client ID 
```
https://iap.googleapis.com/v1/oauth/clientIds/<xxx-xxx.apps.googleusercontent.com>:handleRedirect
```

创建静态外部ip地址，记录ip地址。
```
gcloud compute addresses create sd-agones --global
gcloud compute addresses describe sd-agones --global --format=json | jq .address
```

配置BackendConfig，将client_id和client_secret替换为之前创建的OAuth客户端。
```
kubectl create secret generic iap-secret --from-literal=client_id=<client_id_key> \
    --from-literal=client_secret=<client_secret_key>
```
将 managed-cert.yaml 中的 DOMAIN_NAME1 更改为环境域，然后部署依赖资源。
```
kubectl apply -f ./ingress-iap/managed-cert.yaml
kubectl apply -f ./ingress-iap/backendconfig.yaml
kubectl apply -f ./ingress-iap/service.yaml
kubectl apply -f ./ingress-iap/ingress.yaml
```

授予授权用户访问服务所需的权限。 [指南](https://cloud.google.com/iap/docs/enabling-kubernetes-howto#iap-access) \
**注意：如果你需要添加组织外的IAP users，你需要将你在"Oauth consent screen"界面下将你的应用的"User Type" 由 "internal" 改为 "external"。**

### 为服务域名更新DNS记录
将managed-cert.yaml里设置的服务域名的DNS的A记录调整为ingress的external ip，也就是之前创建的ip，$(gcloud compute addresses describe sd-agones --global --format=json | jq .address)
Google签发和托管的证书需要将域名关联到LB/ingress的ip才可以配置成功，具体参考 [文档，第8步](https://cloud.google.com/kubernetes-engine/docs/how-to/managed-certs?hl=zh-cn)

### 访问服务域名
使用IAP授权的用户访问服务域名

### 清空资源
```
kubectl delete -f ./ingress-iap/managed-cert.yaml
kubectl delete -f ./ingress-iap/backendconfig.yaml
kubectl delete -f ./ingress-iap/service.yaml
kubectl delete -f ./ingress-iap/ingress.yaml

gcloud container clusters delete ${GKE_CLUSTER_NAME} --region=${REGION_NAME}

gcloud compute addresses delete sd-agones --global

gcloud scheduler jobs delete sd-agones-cruiser --location=${REGION}
gcloud functions delete redis_http --region=${REGION} 

gcloud compute networks vpc-access connectors delete sd-agones-connector --region ${REGION} --async

gcloud artifacts repositories delete ${BUILD_REGIST} \
    --location=us-central1 --async

gcloud redis instances delete --project=${PROJECT_ID} sd-agones-cache
gcloud filestore instances delete ${FILESTORE_NAME} --zone=${FILESTORE_ZONE}
```


## 常见问题
### 如果我得到 502，我该如何排除故障？
如果在 pod 准备好之前得到 502 是正常的，你可能需要等待几分钟容器准备好（通常是小于 10 分钟），然后刷新页面。
如果它比预期的要长得多，那么
1. 从 pod 检查 stdout/stderr
查看webui是否启动成功
```
kubectl logs -f pod/sd-agones-fleet-xxxxx-xxxxx -c stable-diffusion-webui
```
2. 从nginx+lua deployment检查stderr
```
kubectl logs -f deployment.apps/stable-diffusion-nginx-deployment
```
3. 检查redis键
在重新用于新部署之前清除 redis 中的所有密钥
```
redis-cli -h ${redis_host}
keys *
flushdb
```
4. 检查cloud scheduler & cloud function，最后一次运行状态应该是“OK”，否则检查日志。

### 为什么Fleet中有一个叫simple-game-server的容器？
这是一个来自 agones 的示例游戏服务器，我们利用它作为游戏服务器 sdk 与 agones 控制平面交互，而无需额外编码和更改 webui。
nginx+lua会调用simple-game-server间接与agones交互进行资源分配和释放。

### 如何将文件上传到 pod？
我们做了一个示范[脚本](./Stable-Diffusion-UI-Agones/sd-webui/extensions/stable-diffusion-webui-udload/scripts/udload.py) 以插件的形式实现文件上传。
除此之外，浏览和下载图片(https://github.com/zanllp/sd-webui-infinite-image-browsing)，下载模型(https://github.com/butaixianran/Stable-Diffusion-Webui-Civitai-Helper)等都可以借助插件的方式实现。

### 如何持久化SD Webui里的setting配置？
由于sd-webui仅在启动时读取config.json/ui-config.json配置文件，启动后的设置项不会主动与文件同步，点击应用设置时会将ui界面的设置同步到文件，因此无法通过软链接的方式持久化这2个文件。
一个折衷办法是配置一个golden配置文件，打包到容器镜像中，避免后续需要频繁修改，[这里](../examples/sd-webui/Dockerfile)有一个参考做法，实现将以下配置持久化，"quicksettings_list": ["sd_model_checkpoint","sd_vae","CLIP_stop_at_last_layers"],