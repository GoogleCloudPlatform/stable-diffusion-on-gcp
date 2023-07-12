[英文部署文档](./README.md)
# Terraform部署指南

我们提供两个版本的部署指南 Agones版本与GKE版本

###  准备工作
确保你已经安装 [google-cloud-sdk](https://cloud.google.com/sdk/docs/install#linux) and [kubectl](https://cloud.google.com/sdk/docs/components) and gke-gcloud-auth-plugin

确保你已经完成google-cloud-sdk设置

安装和设置的示例命令如下:
```bash
#安装google-cloud-sdk
curl -O https://dl.google.com/dl/cloudsdk/channels/rapid/downloads/google-cloud-cli-429.0.0-linux-arm.tar.gz
tar -xf google-cloud-cli-429.0.0-linux-arm.tar.gz 
./google-cloud-sdk/install.sh 
#安装 kubectl 和 gke-gcloud-auth-plugin 插件
gcloud components install kubectl
gcloud components install gke-gcloud-auth-plugin
#设置 gcloud 和 gcloud application-default 认证
gcloud auth application-default login
gcloud auth login
gcloud config set project PROJECT_ID

```

##  Agones 版本
### 01 设置权限

确保你使用的账号有以下权限:

- ROLE: roles/artifactregistry.admin

- ROLE: roles/compute.admin

- ROLE: roles/compute.instanceAdmin.v1

- ROLE: roles/compute.networkAdmin

- ROLE: roles/container.admin

- ROLE: roles/file.editor

为了避免权限问题导致创建资源失败，建议使用 **roles/editor** 或者 **roles/owner** 角色部署资源

### 02 参考[链接](https://cloud.google.com/iap/docs/enabling-kubernetes-howto#oauth-configure)完成IAP设置并创建OAuth Client 并在你的域名解析服务中创建一条A记录指向负载均衡的公网IP(可以在Terraform输出或者控制台中找到IP地址)
Main step as follow
1. 完成OAuth consent screen设置
2. 创建 OAuth 凭据(**注意** *记录一下 client id 与 secret**，后续在local变量中会使用)
3. 更新 OAuth 重定向URL


### 03 替换相应的本地变量 [值为大写的内容必须替换] ,取消[Agone verion]代码块的注释，同时注释掉[GKE version]代码块

编辑main.tf文件替换变量为你的项目相关内容
- 如果你选择区域集群，替换cluster_location变量为区域代码
- 如果你单可用区集群，替换cluster_location变量为可用区代码

下面的示例为使用T4 GPU的单可用区集群，集群位于us-central1-f可用区

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
### 04 创建所有子模块资源 (包括 agones_gcp_res,agones_build_image,helm_agones,agones_k8s_res)

```bash
# 切换至代码目录
cd gcp-stable-diffusion-build-deploy/terraform-provision-infra/

# 初始化
terraform init

# 部署资源
terraform apply --auto-approve -target="module.agones_gcp_res";terraform apply --auto-approve  -target="module.agones_build_image";terraform apply --auto-approve -target="module.helm_agones";terraform apply --auto-approve -target="module.agones_k8s_res"


# 销毁资源
terraform destroy --auto-approve -target="module.agones_k8s_res";terraform destroy --auto-approve  -target="module.helm_agones";terraform destroy --auto-approve -target="module.agones_gcp_res"
```

### 05 设置域名解析和授权用户访问负载均衡
* 在你的域名解析服务中创建一条 A 记录指向 webui_address 的公网IP (sdwebui.example.com - > xxx.xxx.xxx.xxx)
* 在IAP中授权用户 IAP-secured Web App User 权限，以便用户通过子域名访问webui服务
* 等待负载均衡的证书生效后，通过子域名访问你的webui界面（例如https://sdwebui.example.com）

## GKE版本

### 01 设置权限

确保你使用的账号有以下权限:

- ROLE: roles/artifactregistry.admin

- ROLE: roles/compute.admin

- ROLE: roles/compute.instanceAdmin.v1

- ROLE: roles/compute.networkAdmin

- ROLE: roles/container.admin

- ROLE: roles/file.editor

为了避免权限问题导致创建资源失败，建议使用 **roles/editor** 或者 **roles/owner** 角色部署资源

### 02  替换相应的本地变量 [变量oauth_client_id，oauth_client_secret，sd_webui_domain在GKE版本中未使用，可以不用修改或替换] ,注释掉[Agone verion]代码块，同时取消掉[GKE version]代码块的注释

编辑main.tf文件替换变量为你的项目相关内容
- 如果你选择区域集群，替换cluster_location变量为区域代码
- 如果你单可用区集群，替换cluster_location变量为可用区代码

下面的示例为使用T4 GPU的单可用区集群，集群位于us-central1-f可用区

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
### 03 创建所有子模块(包括 nonagones_gcp_res,nonagones_build_image,nonagones_k8s_res)

```bash
# 切换至代码目录
cd gcp-stable-diffusion-build-deploy/terraform-provision-infra/

# 初始化
terraform init

# 创建资源
terraform apply --auto-approve -target="module.nonagones_gcp_res";terraform apply --auto-approve -target="module.nonagones_build_image";terraform apply --auto-approve -target="module.nonagones_k8s_res"


# 销毁资源
terraform destroy --auto-approve -target="module.nonagones_k8s_res"; terraform destroy --auto-approve -target="module.nonagones_gcp_res"
```
## 代码贡献

欢迎提交Pull Request，遇到问题是可以通过提Issue来讨论

注意提交Pull Request前确保代码运行正确

## License

[MIT](https://choosealicense.com/licenses/mit/)
