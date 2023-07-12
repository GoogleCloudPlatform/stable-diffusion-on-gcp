[Chinese Version Guide](./README_zh.md)
# Infrastructure and kubernetes resource deploy guide 

We Offer two version deployment of Stable Diffusion Web UI on GKE

###  Before you begin
Make sure that you have install [google-cloud-sdk](https://cloud.google.com/sdk/docs/install#linux) and [kubectl](https://cloud.google.com/sdk/docs/components) and gke-gcloud-auth-plugin
Make sure that you have finish google-cloud-sdk setup 
Example cmd as follow:
```bash
#install google cloud sdk 
curl -O https://dl.google.com/dl/cloudsdk/channels/rapid/downloads/google-cloud-cli-429.0.0-linux-arm.tar.gz
tar -xf google-cloud-cli-429.0.0-linux-arm.tar.gz 
./google-cloud-sdk/install.sh 
#install kubectl and gke-gcloud-auth-plugin
gcloud components install kubectl
gcloud components install gke-gcloud-auth-plugin
#login gcloud and gcloud application-default
gcloud auth application-default login
gcloud auth login
gcloud config set project PROJECT_ID

```

##  Agones Version
### 01 Set up permissions

Make sure that you have the necessary permissions on your user account:

- ROLE: roles/artifactregistry.admin

- ROLE: roles/compute.admin

- ROLE: roles/compute.instanceAdmin.v1

- ROLE: roles/compute.networkAdmin

- ROLE: roles/container.admin

- ROLE: roles/file.editor

**roles/editor or roles/owner** is prefered

### 02 Manual Step includes Config IAP refer to [Link](https://cloud.google.com/iap/docs/enabling-kubernetes-howto#oauth-configure) and create a DNS A record point to reserved IP (from terraform output webui_ingress_address)
Main step as follow
1. Configuring the OAuth consent screen
2. Creating OAuth credentials (**IMPORTANT** *please make note of client id and secret**)
3. Update OAuth client Authorized redirect URIs
4. Creating A recored point to webui_address in DNS provider (sdwebui.example.com - > xxx.xxx.xxx.xxx)
5. (After kubernetes resource has been created)Grant IAP-secured Web App User permission for user


### 03 Replace parameter [UPPER CASE PARAMETER MUST REPALCE] , keep the [Agone verion] code block Uncomment and #[GKE version] code block comment

edit the main.tf replace the locals parameter with your project's.
- If you choose regional cluster replace the location parameter with region code
- If you choose zonal cluster replace the location parameter with zone code

follow example of us-central1-f zonal cluster with Nvdia T4 Accelerator Node

```bash
locals {
  project_id          = "PROJECT_ID"
  oauth_client_id     = "OAUTH_CLIENT_ID"
  oauth_client_secret = "OAUTH_CLIENT_SECRET"
  sd_webui_domain     = "YOUR_OWNED_CUSTOM_DOMAIN_OR_SUBDOMAIN"
  region              = "us-central1"
  filestore_zone      = "us-central1-f" # Filestore location must be same region or zone with gke
  cluster_location    = "us-central1-f" # GKE Cluster location
  node_machine_type   = "custom-12-49152-ext"
  accelerator_type    = "nvidia-tesla-t4" # Available accelerator_type from gcloud compute accelerator-types list --format='csv(zone,name)'
  gke_num_nodes       = 1
}

```
### 04 Provision all submodule (including agones_gcp_res,agones_build_image,helm_agones,agones_k8s_res)

```bash
# switch to work directory
cd gcp-stable-diffusion-build-deploy/terraform-provision-infra/

# init terraform
terraform init

# deploy Infrastructure
terraform apply --auto-approve -target="module.agones_gcp_res";terraform apply --auto-approve  -target="module.agones_build_image";terraform apply --auto-approve -target="module.helm_agones";terraform apply --auto-approve -target="module.agones_k8s_res"


# destroy Infrastructure
terraform destroy --auto-approve -target="module.agones_k8s_res";terraform destroy --auto-approve  -target="module.helm_agones";terraform destroy --auto-approve -target="module.agones_gcp_res"
```

### 05 Grant Permission and access web ui
* Back to Step 04.5 grant IAP-secured Web App User permission 
* Access webui via your domain or subdomain

## Non Agones Version
s
### 01 Set up permissions

Make sure that you have the necessary permissions on your user account:

- ROLE: roles/artifactregistry.admin

- ROLE: roles/compute.admin

- ROLE: roles/compute.instanceAdmin.v1

- ROLE: roles/compute.networkAdmin

- ROLE: roles/container.admin

- ROLE: roles/file.editor

**roles/editor or roles/owner** is prefered

### 02 Replace parameter [UPPER CASE PARAMETER MUST REPALCE] , comment the [Agone verion] code block and Uncomment [GKE version] code block

edit the main.tf replace the locals parameter with your project's.
- If you choose regional cluster replace the location parameter with region code
- If you choose zonal cluster replace the location parameter with zone code

follow example of us-central1-f zonal cluster with Nvdia T4 Accelerator Node

```bash
locals {
  project_id          = "PROJECT_ID"
  region              = "us-central1"
  filestore_zone      = "us-central1-f" # Filestore location must be same region or zone with gke
  cluster_location    = "us-central1-f" # GKE Cluster location
  node_machine_type   = "custom-12-49152-ext"
  accelerator_type    = "nvidia-tesla-t4" # Available accelerator_type from gcloud compute accelerator-types list --format='csv(zone,name)'
  gke_num_nodes       = 1
}

```
### 03 Provision all submodule (including nonagones_gcp_res,nonagones_build_image,nonagones_k8s_res)

```bash
# switch to work directory
cd gcp-stable-diffusion-build-deploy/terraform-provision-infra/

# init terraform
terraform init

# Provision resource
terraform apply --auto-approve -target="module.nonagones_gcp_res";terraform apply --auto-approve -target="module.nonagones_build_image";terraform apply --auto-approve -target="module.nonagones_k8s_res"


# destroy resource
terraform destroy --auto-approve -target="module.nonagones_k8s_res"; terraform destroy --auto-approve -target="module.nonagones_gcp_res"
```
## Contributing

Pull requests are welcome. For major changes, please open an issue first
to discuss what you would like to change.

Please make sure to update tests as appropriate.

## License

[MIT](https://choosealicense.com/licenses/mit/)
