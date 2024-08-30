#!/bin/bash
# Clone/Update poc repo
if cd cxg_on_k8; then git pull; else git clone git@github.com:bag-cnag/cxg_on_k8.git && cd cxg_on_k8; fi

# Build images
eval $(minikube docker-env)
docker build . -f docker/Dockerfile_cellxgene_slim -t cellxgene:1.1.2-python3.11-slim-bookworm
docker build . -f docker/Dockerfile_aws-cli -t aws_cli:xsmall
docker build . -f docker/Dockerfile_operator -t sui_operator:v1
cd -

# Declare cellxgene namespace with s3bucket.local AWS credentials
kubectl apply -f minikube/namespace.yaml

# Declare oauth2-proxy
kubectl apply -f minikube/oauth2-proxy.yaml

# Declare sui CRD and deploy operator
kubectl apply -f cxg_on_k8/manifests/crd_single-user-instance.yaml
kubectl apply -f cxg_on_k8/manifests/serviceaccount_sui-operator.yaml
kubectl apply -f cxg_on_k8/manifests/service_ingress-nginx-controller_metrics.yaml
kubectl apply -f cxg_on_k8/manifests/deployment_sui_operator.yaml

# Declare service account
kubectl apply -f cxg_on_k8/manifests/serviceaccount_omicsdm.yaml
# Print out token 
echo "---"
kubectl describe secrets omicsdm-token | grep 'token:' | awk '{ print $2 }'
