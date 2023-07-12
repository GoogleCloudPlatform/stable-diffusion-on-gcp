
# User Guide

* Set Environment Variables
  ```
  SOURCE_PROJECT_ID=flius-vpc-2
  IMAGE_NAME=sd-image
  PROJECT_ID=project-kangwe-poc
  CLUSTER_NAME=dpv2-test
  ```
* Copy Image to your project
  ```
  gcloud compute images create sd-image \
  --source-image=projects/${SOURCE_PROJECT_ID}/global/images/${IMAGE_NAME} \
  --project=${PROJECT_ID}
  ```
<!-- * Enable Workload identity
```
gcloud container clusters create ${CLUSTER_NAME} \
    --zone=${ZONE} \
    --workload-pool=${PROJECT_ID}.svc.id.goog
gcloud container node-pools update ${NODEPOOL_NAME} \
    --cluster=${CLUSTER_NAME} \
    --zone=${ZONE} \
    --workload-metadata=GKE_METADATA
kubectl create serviceaccount workload-identity-ksa \
    --namespace default
gcloud iam service-accounts create workload-identity-gsa \
    --project=${PROJECT_ID}     
gcloud projects add-iam-policy-binding ${PROJECT_ID} \
    --member "serviceAccount:workload-identity-gsa@${PROJECT_ID}.iam.gserviceaccount.com" \
    --role "roles/compute.admin"   
gcloud iam service-accounts add-iam-policy-binding workload-identity-gsa@${PROJECT_ID}.iam.gserviceaccount.com \
    --role roles/iam.workloadIdentityUser \
    --member "serviceAccount:${PROJECT_ID}.svc.id.goog[default/workload-identity-ksa]"
kubectl annotate serviceaccount workload-identity-ksa \
    --namespace default \
    iam.gke.io/gcp-service-account=workload-identity-gsa@${PROJECT_ID}.iam.gserviceaccount.com
``` -->
* Build init container image to attach disks based on image
```
cd attach-disk
gcloud builds submit --tag=us-central1-docker.pkg.dev/${PROJECT_ID}/stable-diffusion-repo/attach-disk-image
```
* Install DaemonSet, please update values in daemonset.yaml as described below.
  - Update image repo as you specified in previous step.
    ```
    initContainers:
    - name: init-disk
      image: us-central1-docker.pkg.dev/flius-vpc-2/stable-diffusion-repo/attach-disk-image

    kubectl apply -f daemonset.yaml
    ```
* Install Stable Diffusion deployment
```
kubectl apply -f deployment-init-disk.yaml
```
