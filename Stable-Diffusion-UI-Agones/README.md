# Stable-Diffusion on Agones Implementation Guide

This guide give simple steps for stable-diffusion users to launch a stable diffusion deployment by using GCP GKE service, and using Filestore as shared storage for model and output files. For convinent multi-user stable-diffusion runtime management, using the [Agones](https://agones.dev/site/) as the runtime management operator, each isolated stable-diffusion runtime is hosted in an isolated POD, each authorized user will be allocated a dedicated POD. User can just follow the step have your stable diffusion model running.

* [Introduction](#Introduction)
* [How-To](#how-to)

## Introduction
   This project is using the [Stable-Diffusion-WebUI](https://github.com/AUTOMATIC1111/stable-diffusion-webui) open source as the user interactive front-end, customer can just prepare the stable diffusion model to build/deployment stable diffusion model by container. This project use the cloud build to help you quick build up a docker image with your stable diffusion model, then you can make a deployment base on the docker image. To give mutli-user isolated stable-diffussion runtime, using the [Agones](https://agones.dev/site/) as the stable-diffusion fleet management operator, Agones manage the stable diffussion runtime's lifecycle and control the autoscaling based on user demand.

## Architecture
![sd-agones-arch](images/sd-agones-arch.png)

## How To
you can use the cloud shell as the run time to do below steps.
### Before you begin
1. Make sure you have an available GCP project for your deployment
2. Enable the required service API using [cloud shell](https://cloud.google.com/shell/docs/run-gcloud-commands)
```
gcloud services enable compute.googleapis.com artifactregistry.googleapis.com container.googleapis.com file.googleapis.com vpcaccess.googleapis.com redis.googleapis.com cloudscheduler.googleapis.com cloudfunctions.googleapis.com cloudbuild.googleapis.com
```
3. Exempt below organization policy constraints in your project
```
constraints/compute.vmExternalIpAccess
constraints/compute.requireShieldedVm  
constraints/cloudfunctions.allowedIngressSettings
```
### Initialize the environment

```
PROJECT_ID=<replace this with your PROJECT ID>
GKE_CLUSTER_NAME=<replace this with your GKE cluster name>
REGION=<replace this with your region>
VPC_NETWORK=<replace this with your VPC network name>
VPC_SUBNETWORK=<replace this with your VPC subnetwork name>
BUILD_REGIST=<replace this with your preferred Artifact Registry repository name>
FILESTORE_NAME=<replace with Filestore instance name>
FILESTORE_ZONE=<replace with Filestore instance zone>
FILESHARE_NAME=<replace with fileshare name>
```
### Create GKE Cluster
Do the following step using the cloud shell. This guide using the T4 GPU node as the VM host, by your choice you can change the node type with [other GPU instance type](https://cloud.google.com/compute/docs/gpus). \
In this guide we also by default enabled [Filestore CSI driver](https://cloud.google.com/kubernetes-engine/docs/how-to/persistent-volumes/filestore-csi-driver) for models/outputs sharing. \
If you wish to use [GcsFuse CSI driver](https://cloud.google.com/kubernetes-engine/docs/how-to/persistent-volumes/cloud-storage-fuse-csi-driver) instead, please follow the notes below for GcsFuse.

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
**NOTE: If you are going to use GCS CSI instead, create the cluster with the steps below**
```
# Create GKE cluster with workload identity enabled
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

# For existing cluster,

gcloud container clusters update ${GKE_CLUSTER_NAME} \
    --region=${REGION} \
    --workload-pool="${PROJECT_ID}.svc.id.goog"

# Enable GcsFuseCsiDriver

gcloud container clusters update ${GKE_CLUSTER_NAME} \
    --update-addons GcsFuseCsiDriver=ENABLED \
    --region=${REGION}

# GPU node pool suggest 200GB disk size, because GcsFuse sidecar need default 50GiB for buffer,
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

### Firewall rule setup for Agones
1. For public cluster, allow 0.0.0.0/0
2. For private cluster, allow access from all internal CIDR(10.0.0.0/8, 172.16.0.0/16, 192.168.0.0/24). Specifically, CIDR range for pod, but using all internal CIDR will be easier.
3. TCP port 443/8080/8081 & 7000-8000 and UDP port 7000-8000
4. For Target use gke node tag as target tag, e.g. gke-gke-01-7267dc32-node, you can find it in your VM console.

**Note: for private cluster, a Cloud NAT is required for the GKE subnet. sd-webui need access to internet to automatically download necessary model files**

```
gcloud compute firewall-rules create allow-agones \
	--direction=INGRESS --priority=1000 --network=${VPC_NETWORK} --action=ALLOW \
	--rules=tcp:443,tcp:8080,tcp:8081,tcp:7000-8000,udp:7000-8000 \
	--source-ranges=0.0.0.0/0 \
	--target-tags=${GKE_NODE_NETWORK_TAG}
```

### Get credentials of GKE cluster
```
gcloud container clusters get-credentials ${GKE_CLUSTER_NAME} --region ${REGION}
```

### Install GPU Driver
For T4 and earlier GPU instances, run
```
kubectl apply -f https://raw.githubusercontent.com/GoogleCloudPlatform/container-engine-accelerators/master/nvidia-driver-installer/cos/daemonset-preloaded.yaml
```
If using lateset GPU instances, i.e. G2/L4, use below command instead for a more recent driver.
```
kubectl apply -f https://raw.githubusercontent.com/GoogleCloudPlatform/container-engine-accelerators/master/nvidia-driver-installer/cos/daemonset-preloaded-latest.yaml
```

### Create Cloud Artifacts as Docker Repo
```
gcloud artifacts repositories create ${BUILD_REGIST} --repository-format=docker \
--location=${REGION}

gcloud auth configure-docker ${REGION}-docker.pkg.dev
```

### Grant the GKE cluster with Cloud Artifacts read access
By default, GKE cluster is using default compute engine service account to access Artifacts registry.
Update SERVICE_ACCOUNT_EMAIL with you default compute engine service account and run below command.
```
gcloud artifacts repositories add-iam-policy-binding ${BUILD_REGIST} \
    --location=${REGION} \
    --member=serviceAccount:SERVICE_ACCOUNT_EMAIL \
    --role="roles/artifactregistry.reader"
```
For details, please refer to https://cloud.google.com/kubernetes-engine/docs/troubleshooting#permission_denied_error

### Build Stable Diffusion Image
Build image with provided Dockerfile, push to repo in Cloud Artifacts

```
cd Stable-Diffusion-on-GCP/Stable-Diffusion-UI-Agones/sd-webui
docker build . -t ${REGION}-docker.pkg.dev/${PROJECT_ID}/${BUILD_REGIST}/sd-webui:0.1
docker push ${REGION}-docker.pkg.dev/${PROJECT_ID}/${BUILD_REGIST}/sd-webui:0.1

```
You can also build it with Cloud Build.
```
gcloud builds submit \
--machine-type=e2-highcpu-32 \
--disk-size=100 \
--region=us-central1 \
-t ${REGION}-docker.pkg.dev/${PROJECT_ID}/${BUILD_REGIST}/sd-webui:0.1
```

**Note: If you are using GcsFuse CSI, you don't need to create Filestore**
### Create Filestore
Create Filestore storage, mount and prepare files and folders for models/outputs/training data
You should prepare a VM to mount the filestore instance.

```
gcloud filestore instances create ${FILESTORE_NAME} --zone=${FILESTORE_ZONE} --tier=BASIC_HDD --file-share=name=${FILESHARE_NAME},capacity=1TB --network=name=${VPC_NETWORK}
e.g. 
gcloud filestore instances create nfs-store --zone=us-central1-b --tier=BASIC_HDD --file-share=name="vol1",capacity=1TB --network=name=${VPC_NETWORK}

```
Deploy the PV and PVC resource, replace the nfs-server-ip using the nfs instance's ip address that created before in the file nfs_pv.yaml.
Update the "path: /vol1" with fileshare created with the filestore. The yaml file is located in ./Stable-Diffusion-UI-Agones/agones/ folder.
```
kubectl apply -f ./Stable-Diffusion-UI-Agones/agones/nfs_pv.yaml
kubectl apply -f ./Stable-Diffusion-UI-Agones/agones/nfs_pvc.yaml
```
**Note: You will need to initialize the files and folders in the Filestore share in order for sd-webui to run** \
One easy way to do this,
1. Create a VM in the same subnet with Filestore instance
2. Mount Filestore share following this [guide](https://cloud.google.com/filestore/docs/mounting-fileshares)
```
sudo apt-get -y update && sudo apt-get install nfs-common -y
sudo mkdir -p /mnt/vol1
sudo mount -o rw,intr ${FILESTORE_IP}:/vol1 /mnt/vol1
```
3. Clone the A1111 repo, copy folders models/ & embeddings/ under the Filestore share mount. (This is because during initialization we will create a symlink for these two folders but the two folders are not empty)
```
git clone https://github.com/AUTOMATIC1111/stable-diffusion-webui.git
cd stable-diffusion-webui
cp -rp models embeddings /mnt/vol1
```
4. Test run and initialize the file and folders by the way  
```
docker run -it --gpus all -p7860:7860 -v /mnt/vol1/models/:/stable-diffusion-webui/models/ -v /mnt/vol1/embeddings/:/stable-diffusion-webui/embeddings/ ${REGION}-docker.pkg.dev/${PROJECT_ID}/${BUILD_REGIST}/sd-webui:0.1 /bin/bash
python3 webui.py --listen
```
After these steps, files and folders should be inplace and your pods should not get CrashLoopBackoff problems.

**Note: If you are using Filestore CSI, you don't need to create Gcs bucket**
### Create GcsFuse bucket
Follow step 1 & 2 from this [GcsFuse guide](https://github.com/GoogleCloudPlatform/gcs-fuse-csi-driver/blob/main/docs/authentication.md) to setup bucket and IAM. \
After that, update the bucket name variable in gcs_pv.yaml, and run
```
kubectl apply -f ./Stable-Diffusion-UI-Agones/agones/gcs_pv.yaml
kubectl apply -f ./Stable-Diffusion-UI-Agones/agones/gcs_pvc.yaml
```

### Install Agones
Install the Agones operator on default-pool, the default pool is long-run node pool that host the Agones Operator.
Note: for quick start, you can using the cloud shell which has helm installed already.
```
helm repo add agones https://agones.dev/chart/stable
helm repo update
kubectl create namespace agones-system
cd Stable-Diffusion-on-GCP/Stable-Diffusion-UI-Agones
# Current agones setup require agones<=1.33.0
helm install sd-agones-release --namespace agones-system -f ./agones/values.yaml agones/agones --version 1.33.0
```

### Create Redis Cache
Create a redis cache instance to host the access information.
```
gcloud redis instances create --project=${PROJECT_ID}  sd-agones-cache --tier=standard --size=1 --region=${REGION} --redis-version=redis_6_x --network=projects/${PROJECT_ID}/global/networks/${VPC_NETWORK} --connect-mode=DIRECT_PEERING
```

Record the redis instance connection ip address.
```
gcloud redis instances describe sd-agones-cache --region ${REGION} --format=json | jq .host
```

### Build Nginx proxy image
Build image with provided Dockerfile, push to repo in Cloud Artifacts. Please replace ${REDIS_HOST} in the gcp-stable-diffusion-build-deploy/Stable-Diffusion-UI-Agones/nginx/sd.lua with the ip address record in previous step.

```
cd Stable-Diffusion-on-GCP/Stable-Diffusion-UI-Agones/nginx
REDIS_IP=$(gcloud redis instances describe sd-agones-cache --region ${REGION} --format=json 2>/dev/null | jq .host)
sed -i "s@\"\${REDIS_HOST}\"@${REDIS_IP}@g" sd.lua

docker build . -t ${REGION}-docker.pkg.dev/${PROJECT_ID}/${BUILD_REGIST}/sd-nginx:0.1
docker push ${REGION}-docker.pkg.dev/${PROJECT_ID}/${BUILD_REGIST}/sd-nginx:0.1
```
Or use Cloud Build.
```
gcloud builds submit \
--machine-type=e2-highcpu-32 \
--disk-size=100 \
--region=us-central1 \
-t ${REGION}-docker.pkg.dev/${PROJECT_ID}/${BUILD_REGIST}/sd-nginx:0.1
```

### Build agones-sidecar image
Build the optional agones-sidecar image with provided Dockerfile, push to repo in Cloud Artifacts. This is to hijack the 502 returned from sd-webui before it finished launching to provide a graceful experience.

```
cd Stable-Diffusion-on-GCP/Stable-Diffusion-UI-Agones/agones-sidecar
docker build . -t ${REGION}-docker.pkg.dev/${PROJECT_ID}/${BUILD_REGIST}/sd-agones-sidecar:0.1
docker push ${REGION}-docker.pkg.dev/${PROJECT_ID}/${BUILD_REGIST}/sd-agones-sidecar:0.1
```
Or use Cloud Build.
```
gcloud builds submit \
--machine-type=e2-highcpu-32 \
--disk-size=100 \
--region=us-central1 \
-t ${REGION}-docker.pkg.dev/${PROJECT_ID}/${BUILD_REGIST}/sd-agones-sidecar:0.1
```

### Deploy stable-diffusion agones deployment(Filestore CSI)
Deploy stable-diffusion agones deployment, please replace the image URL in the deployment.yaml and fleet yaml with the image built(nginx, optional agones-sidecar and sd-webui) before.
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

### Deploy stable-diffusion agones deployment(GcsFuse CSI)
Deploy stable-diffusion agones deployment, please replace the image URL in the deployment.yaml and fleet yaml with the image built(nginx, optional agones-sidecar and sd-webui) before. \
Before apply the deployment, setup Kubernetes service account binding with IAM account, referencing step 4 from this [GcsFuse guide](https://github.com/GoogleCloudPlatform/gcs-fuse-csi-driver/blob/main/docs/authentication.md). \
We should use existing Kubernetes service account for Agones, i.e. agones-sdk instead of creating new one, because we are using agones-sdk to create fleets.
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
After that, remaining steps are the same, just remind to use fleet_gcs.yaml instead.
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


### Prepare Cloud Function Serverless VPC Access
Create serverless VPC access connector, which is used by cloud function to connect Redis through the private connection endpoint.
```
gcloud compute networks vpc-access connectors create sd-agones-connector --network ${VPC_NETWORK} --region ${REGION} --range 192.168.240.16/28
```

### Deploy Cloud Function Cruiser Program
This Cloud Function work as Cruiser to monitor the idle user, by default when the user is idle for 15mins, the stable-diffusion runtime will be collected back. Please replace ${REDIS_HOST} with the redis instance ip address that record in previous step. To custom the idle timeout default setting, please overwrite setting by setting the variable TIME_INTERVAL.
```
cd Stable-Diffusion-on-GCP/Stable-Diffusion-UI-Agones/cloud-function
REDIS_HOST=$(gcloud redis instances describe sd-agones-cache --region ${REGION} --format=json 2>/dev/null | jq .host)
gcloud functions deploy redis_http --runtime python310 --trigger-http --allow-unauthenticated --region=${REGION} --vpc-connector=sd-agones-connector --egress-settings=private-ranges-only --set-env-vars=REDIS_HOST=${REDIS_HOST}
```
Record the Function trigger url.
```
gcloud functions describe redis_http --region us-central1 --format=json | jq .httpsTrigger.url
```
Create the cruiser scheduler. Please change ${FUNCTION_URL} with url in previous step.
```
gcloud scheduler jobs create http sd-agones-cruiser \
    --location=${REGION} \
    --schedule="*/5 * * * *" \
    --uri=${FUNCTION_URL}
```

### Deploy IAP(identity awared proxy)
To allocate isolated stable-diffusion runtime and provide user access auth capability, using the Google Cloud IAP service as an access gateway to provide the identity check and prograge the idenity to the stable-diffusion backend.

Config the [OAuth consent screen](https://developers.google.com/workspace/guides/configure-oauth-consent) and [OAuth credentials](https://developers.google.com/workspace/guides/create-credentials#oauth-client-id), then configure [identity aware proxy for backend serivce on GKE](https://cloud.google.com/iap/docs/enabling-kubernetes-howto#oauth-configure).

After created OAuth 2.0 Client IDs under OAuth credentials, update the Client ID with "Authorized redirect URIs", value should be like,
```
https://iap.googleapis.com/v1/oauth/clientIds/<xxx-xxx.apps.googleusercontent.com>:handleRedirect
```
where xxx-xxx.apps.googleusercontent.com is the Oauth 2.0 client ID you just created.

**Note: if you wish to add IAP users out of your organziation, set your application's "User Type" from "internal" to "external" in "Oauth consent screen".**

Create an static external ip address, record the ip address.
```
gcloud compute addresses create sd-agones --global
gcloud compute addresses describe sd-agones --global --format=json | jq .address
```

Config BackendConfig, replace the client_id and client_secret with the OAuth client create before.
```
kubectl create secret generic iap-secret --from-literal=client_id=client_id_key \
    --from-literal=client_secret=client_secret_key
```
Change the DOMAIN_NAME1 in managed-cert.yaml with the environment domain, then deploy the depend resources.
```
kubectl apply -f ./ingress-iap/managed-cert.yaml
kubectl apply -f ./ingress-iap/backendconfig.yaml
kubectl apply -f ./ingress-iap/service.yaml
kubectl apply -f ./ingress-iap/ingress.yaml
```
Give the authorized users required priviledge to access the service. [Guide](https://cloud.google.com/iap/docs/enabling-kubernetes-howto#iap-access)

### Update DNS record for the domain
Update your DNS record, set A record value to $(gcloud compute addresses describe sd-agones --global --format=json | jq .address) for the domain used in managed-cert.yaml
The Google-managed certificate won't be provisioned successfully unless the domain is already associated with the ingress external IP,
check out the [guide, see step 8](https://cloud.google.com/kubernetes-engine/docs/how-to/managed-certs)

### Access the service domain
Use accounts setup with IAP access to access service domain.

### Clean up
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

gcloud redis instances delete --project=${PROJECT_ID} sd-agones-cache --region ${REGION}
gcloud filestore instances delete ${FILESTORE_NAME} --zone=${FILESTORE_ZONE}
```


## FAQ
### How could I troubleshooting if I get 502?
It is normal if you get 502 before pod is ready, you may have to wait for a few minutes for containers to be ready(usually less than 10mins), then refresh the page.
If it is much longer then expected, then

1. Check stdout/stderr from pod
To see if webui has been launched successfully
```
kubectl logs -f pod/sd-agones-fleet-xxxxx-xxxxx -c stable-diffusion-webui
```
2. Check stderr from nginx+lua deployment
```
kubectl logs -f deployment.apps/stable-diffusion-nginx-deployment
```
3. Check redis keys
Clear all keys from redis before reusing it for new deployment
```
redis-cli -h ${redis_host}
keys *
flushdb
```
4. Check cloud scheduler & cloud function, the last run status should be "OK", otherwise check the logs.

### Why there is a simple-game-server container in the fleet?
This is an example game server from agones, we leverage it as a game server sdk to interact with agones control plane without additional coding and change to webui.
The nginx+lua will call simple-game-server to indirectly interact with agones for resource allication and release.

### How can I upload file to the pod?
We made an example [script](./Stable-Diffusion-UI-Agones/sd-webui/extensions/stable-diffusion-webui-udload/scripts/udload.py) to work as an extension for file upload.
Besides, you can use extensions for image browsing and downloading(https://github.com/zanllp/sd-webui-infinite-image-browsing), model/lora downloading(https://github.com/butaixianran/Stable-Diffusion-Webui-Civitai-Helper) and more.

### How to persist the settings in SD Webui?
sd-webui only load config.json/ui-config.json on startup. If you click apply settings, it would write the current settings in UI to the config files, so we could not persist the two files with symlink trick.
One workaround is to make golden config files and pack them to the Docker image. We have an [example](../examples/sd-webui/Dockerfile) to make settings of "quicksettings_list": ["sd_model_checkpoint","sd_vae","CLIP_stop_at_last_layers"] persist.
