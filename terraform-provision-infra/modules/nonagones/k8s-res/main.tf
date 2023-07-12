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

terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "4.63.1"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "2.20.0"
    }
    http = {
      source  = "hashicorp/http"
      version = "3.3.0"
    }
  }
}
data "google_client_config" "default" {}

data "google_container_cluster" "my_cluster" {
  name     = var.gke_cluster_name
  location = var.gke_cluster_location
  project  = var.project_id
}

provider "kubernetes" {
  host  = "https://${data.google_container_cluster.my_cluster.endpoint}"
  token = data.google_client_config.default.access_token
  cluster_ca_certificate = base64decode(
    data.google_container_cluster.my_cluster.master_auth[0].cluster_ca_certificate,
  )
  experiments {
    manifest_resource = true
  }
}

resource "kubernetes_storage_class" "nfs" {
  metadata {
    name = "filestore"
  }
  reclaim_policy      = "Retain"
  storage_provisioner = "nfs"
}

resource "kubernetes_persistent_volume_v1" "nfs_pv" {
  metadata {
    name = "filestore-nfs-pv"
  }
  spec {
    capacity = {
      storage = "1Ti"
    }
    storage_class_name = kubernetes_storage_class.nfs.metadata[0].name
    access_modes       = ["ReadWriteMany"]
    persistent_volume_source {
      nfs {
        path   = "/vol1"
        server = var.google_filestore_reserved_ip_range
      }
    }
  }
}

resource "kubernetes_persistent_volume_claim_v1" "nfs_pvc" {
  metadata {
    name = "vol1"
  }
  spec {
    access_modes       = ["ReadWriteMany"]
    storage_class_name = kubernetes_storage_class.nfs.metadata[0].name
    volume_name        = kubernetes_persistent_volume_v1.nfs_pv.metadata.0.name
    resources {
      requests = {
        storage = "1Ti"
      }
    }
  }
}

data "http" "gpu_driver_file" {
  url = "https://raw.githubusercontent.com/GoogleCloudPlatform/container-engine-accelerators/master/nvidia-driver-installer/cos/daemonset-preloaded-latest.yaml"
}
resource "kubernetes_manifest" "gpu_driver" {
  manifest = yamldecode(data.http.gpu_driver_file.response_body)
}

resource "kubernetes_manifest" "webui_deployment" {
  manifest = yamldecode(<<-EOF
    apiVersion: apps/v1
    kind: Deployment
    metadata:
      name: stable-diffusion-sd15-deployment
      namespace: default
      labels:
        app: stable-diffusion-sd15
    spec:
      replicas: 1
      selector:
        matchLabels:
          app: stable-diffusion-sd15
      template:
        metadata:
          labels:
            app: stable-diffusion-sd15
        spec:
          nodeSelector:
            cloud.google.com/gke-nodepool: "${var.gke_cluster_nodepool}"
          volumes:
            - name: stable-diffusion-storage
              persistentVolumeClaim:
                claimName: vol1
          containers:
          - name: stable-diffusion-webui
            image: "${var.webui_image_url}"
            resources:
              requests:
                cpu: 5
                memory: 24Gi
                nvidia.com/gpu: 1
              limits:
                cpu: 5
                memory: 24Gi
                nvidia.com/gpu: 1
            ports:
              - containerPort: 7860
            volumeMounts:
              - mountPath: "/stable-diffusion-webui/models/Stable-diffusion"
                name: stable-diffusion-storage
                subPath: models/Stable-diffusion/sd15
              - mountPath: "/stable-diffusion-webui/outputs"
                name: stable-diffusion-storage
                subPath: outputs
    EOF
  )
}

resource "kubernetes_manifest" "webui_backend_config" {
  manifest = yamldecode(<<-EOF
    apiVersion: cloud.google.com/v1
    kind: BackendConfig
    metadata:
      name: sd-webui-backendconfig
      namespace: default
    spec:
      sessionAffinity:
        affinityType: "GENERATED_COOKIE"
        affinityCookieTtlSec: 1000
    EOF
  )
}

resource "kubernetes_manifest" "webui_svc" {
  manifest = yamldecode(<<-EOF
    apiVersion: v1
    kind: Service
    metadata:
      name: sd-webui
      namespace: default
      annotations:
        cloud.google.com/backend-config: '{"ports": {"80":"sd-webui-backendconfig"}}'
    spec:
      ports:
      - port: 80
        protocol: TCP
        targetPort: 7860
      selector:
        app: stable-diffusion-sd15
      type: ClusterIP
    EOF
  )
}
resource "kubernetes_manifest" "webui_ingress" {
  manifest = yamldecode(<<-EOF
    apiVersion: networking.k8s.io/v1
    kind: Ingress
    metadata:
      name: sd-webui
      namespace: default
    spec:
      defaultBackend:
        service:
          name: sd-webui
          port:
            number: 80
    EOF
  )
}

data "kubernetes_ingress_v1" "sd_webui" {
  metadata {
    name = "sd-webui"
    namespace = "default"
  }
  depends_on = [kubernetes_manifest.webui_ingress]
}

#resource "kubernetes_manifest" "ingress_sd_agones_ingress" {
#  manifest = {
#    "apiVersion" = "networking.k8s.io/v1"
#    "kind"       = "Ingress"
#    "metadata" = {
#      "annotations" = {
#        "kubernetes.io/ingress.class"                 = "gce"
#        "kubernetes.io/ingress.global-static-ip-name" = var.webui_address_name
#        "networking.gke.io/managed-certificates"      = "managed-cert"
#      }
#      "name"      = "sd-agones-ingress"
#      "namespace" = "default"
#    }
#    "spec" = {
#      "defaultBackend" = {
#        "service" = {
#          "name" = "stable-diffusion-nginx-service"
#          "port" = {
#            "number" = 8080
#          }
#        }
#      }
#    }
#  }
#}

#resource "kubernetes_manifest" "fleet_sd_agones_fleet" {
#  manifest = {
#    "apiVersion" = "agones.dev/v1"
#    "kind"       = "Fleet"
#    "metadata" = {
#      "name"      = "sd-agones-fleet"
#      "namespace" = "default"
#    }
#    "spec" = {
#      "replicas" = 1
#      "template" = {
#        "spec" = {
#          "container" = "simple-game-server"
#          "ports" = [
#            {
#              "container"     = "simple-game-server"
#              "containerPort" = 7654
#              "name"          = "default"
#            },
#            {
#              "container"     = "stable-diffusion-webui"
#              "containerPort" = 7860
#              "name"          = "sd"
#              "protocol"      = "TCP"
#            },
#          ]
#          "template" = {
#            "spec" = {
#              "containers" = [
#                {
#                  "image" = "us-docker.pkg.dev/agones-images/examples/simple-game-server:0.14"
#                  "name"  = "simple-game-server"
#                  "resources" = {
#                    "limits" = {
#                      "cpu"    = "20m"
#                      "memory" = "64Mi"
#                    }
#                    "requests" = {
#                      "cpu"    = "20m"
#                      "memory" = "64Mi"
#                    }
#                  }
#                },
#                {
#                  "command" = [
#                    "/bin/sh",
#                    "start.sh",
#                  ]
#                  "image" = var.webui_image_url
#                  "name"  = "stable-diffusion-webui"
#                  "resources" = {
#                    "limits" = {
#                      "nvidia.com/gpu" = "1"
#                    }
#                  }
#                  "volumeMounts" = [
#                    {
#                      "mountPath" = "/stable-diffusion-webui/models"
#                      "name"      = "stable-diffusion-storage"
#                      "subPath"   = "models"
#                    },
#                    {
#                      "mountPath" = "/result"
#                      "name"      = "stable-diffusion-storage"
#                      "subPath"   = "result"
#                    },
#                  ]
#                },
#              ]
#              "volumes" = [
#                {
#                  "name" = "stable-diffusion-storage"
#                  "persistentVolumeClaim" = {
#                    "claimName" = "vol1"
#                  }
#                },
#              ]
#            }
#          }
#        }
#      }
#    }
#  }
#}
#
#resource "kubernetes_manifest" "fleetautoscaler_fleet_autoscaler_policy" {
#  depends_on = [kubernetes_manifest.fleet_sd_agones_fleet]
#  manifest = {
#    "apiVersion" = "autoscaling.agones.dev/v1"
#    "kind"       = "FleetAutoscaler"
#    "metadata" = {
#      "name"      = "fleet-autoscaler-policy"
#      "namespace" = "default"
#    }
#    "spec" = {
#      "fleetName" = "sd-agones-fleet"
#      "policy" = {
#        "buffer" = {
#          "bufferSize"  = 1
#          "maxReplicas" = 20
#          "minReplicas" = 1
#        }
#        "type" = "Buffer"
#      }
#      "sync" = {
#        "fixedInterval" = {
#          "seconds" = 30
#        }
#        "type" = "FixedInterval"
#      }
#    }
#  }
#}
#
#resource "kubernetes_manifest" "backendconfig_config_default" {
#  manifest = {
#    "apiVersion" = "cloud.google.com/v1"
#    "kind"       = "BackendConfig"
#    "metadata" = {
#      "name"      = "config-default"
#      "namespace" = "default"
#    }
#    "spec" = {
#      "iap" = {
#        "enabled" = true
#        "oauthclientCredentials" = {
#          "secretName" = "iap-secret"
#        }
#      }
#      "timeoutSec" = 900
#    }
#  }
#}
#resource "kubernetes_manifest" "managedcertificate_managed_cert" {
#  manifest = {
#    "apiVersion" = "networking.gke.io/v1"
#    "kind"       = "ManagedCertificate"
#    "metadata" = {
#      "name"      = "managed-cert"
#      "namespace" = "default"
#    }
#    "spec" = {
#      "domains" = [
#        var.sd_webui_domain
#      ]
#    }
#  }
#}
#
#resource "kubernetes_manifest" "service_stable_diffusion_nginx_service" {
#  manifest = {
#    "apiVersion" = "v1"
#    "kind"       = "Service"
#    "metadata" = {
#      "annotations" = {
#        "beta.cloud.google.com/backend-config" = "{\"default\": \"config-default\"}"
#        "cloud.google.com/neg"                 = "{\"ingress\": true}"
#      }
#      "labels" = {
#        "app" = "stable-diffusion-nginx"
#      }
#      "name"      = "stable-diffusion-nginx-service"
#      "namespace" = "default"
#    }
#    "spec" = {
#      "ports" = [
#        {
#          "port"       = 8080
#          "protocol"   = "TCP"
#          "targetPort" = 8080
#        },
#      ]
#      "selector" = {
#        "app" = "stable-diffusion-nginx"
#      }
#      "type" = "ClusterIP"
#    }
#  }
#}