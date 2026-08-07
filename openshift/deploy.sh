#!/bin/bash
set -euo pipefail

# ============================================================
# OpenShift Deploy Script for Logistics System
# Supports: CRC (Local), OpenShift Online, Cloud OpenShift
# ============================================================

NAMESPACE="logistics"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "============================================"
echo " Logistics System - OpenShift Deployment"
echo "============================================"

# Check oc command
if ! command -v oc &> /dev/null; then
    echo "ERROR: 'oc' command not found."
    echo "  - CRC: run 'eval \$(crc oc-env)'"
    echo "  - Install: https://mirror.openshift.com/pub/openshift-v4/clients/ocp/stable/"
    exit 1
fi

# Check if logged in
if ! oc whoami &> /dev/null; then
    echo "ERROR: Not logged in to OpenShift."
    echo "  - CRC: oc login -u kubeadmin -p \$(oc whoami -t)"
    exit 1
fi

# Detect environment
echo ""
echo "Environment: $(oc version --short 2>/dev/null || echo 'OpenShift')"
echo "User: $(oc whoami)"
echo "Server: $(oc whoami --show-server)"
echo ""

# Step 1: Create namespace
echo "[1/7] Creating namespace..."
oc apply -f "$SCRIPT_DIR/00-namespace.yaml"

# Step 2: Apply secrets
echo "[2/7] Applying secrets..."
oc apply -f "$SCRIPT_DIR/01-secrets.yaml"

# Step 3: Apply configmap
echo "[3/7] Applying configmap..."
oc apply -f "$SCRIPT_DIR/02-configmap.yaml"

# Step 4: Deploy PostgreSQL
echo "[4/7] Deploying PostgreSQL..."
oc apply -f "$SCRIPT_DIR/03-postgresql.yaml"

# Step 5: Deploy Redis
echo "[5/7] Deploying Redis..."
oc apply -f "$SCRIPT_DIR/04-redis.yaml"

# Step 6: Build and Deploy Backend
echo "[6/7] Building & Deploying Backend..."
# Try to create imagestream (ignore if exists)
oc apply -f "$SCRIPT_DIR/08-buildconfigs.yaml" 2>/dev/null || true

# Build backend image
echo "  Building backend image..."
oc start-build backend -n $NAMESPACE --follow 2>/dev/null || {
    echo "  Build config not found. Building locally with podman..."
    if command -v podman &> /dev/null; then
        REGISTRY=$(oc get route default-route -n openshift-image-registry -o jsonpath='{.spec.host}' 2>/dev/null || echo "image-registry.openshift-image-registry.svc:5000")
        podman login -u kubeadmin -p $(oc whoami -t) $REGISTRY --tls-verify=false 2>/dev/null || true
        podman build -t $REGISTRY/logistics/backend:latest "$SCRIPT_DIR/../backend"
        podman push $REGISTRY/logistics/backend:latest --tls-verify=false
    fi
}

oc apply -f "$SCRIPT_DIR/05-backend.yaml"

# Step 7: Deploy Celery + Frontend
echo "[7/7] Deploying Celery Worker & Frontend..."
oc apply -f "$SCRIPT_DIR/06-celery-worker.yaml"

# Build frontend image
echo "  Building frontend image..."
oc start-build frontend -n $NAMESPACE --follow 2>/dev/null || {
    echo "  Building locally with podman..."
    if command -v podman &> /dev/null; then
        REGISTRY=$(oc get route default-route -n openshift-image-registry -o jsonpath='{.spec.host}' 2>/dev/null || echo "image-registry.openshift-image-registry.svc:5000")
        podman build -t $REGISTRY/logistics/frontend:latest -f "$SCRIPT_DIR/Dockerfile.frontend-openshift" "$SCRIPT_DIR/../frontend"
        podman push $REGISTRY/logistics/frontend:latest --tls-verify=false
    fi
}

oc apply -f "$SCRIPT_DIR/07-frontend.yaml"

echo ""
echo "============================================"
echo " Deployment Complete!"
echo "============================================"
echo ""
echo " Waiting for pods to be ready..."
oc wait --for=condition=Ready pod --all -n $NAMESPACE --timeout=300s 2>/dev/null || true
echo ""
echo " Pods status:"
oc get pods -n $NAMESPACE
echo ""
echo " Routes:"
oc get routes -n $NAMESPACE
echo ""
echo " To access the app:"
echo "   Frontend URL: https://$(oc get route frontend -n $NAMESPACE -o jsonpath='{.spec.host}' 2>/dev/null || echo '<pending>')"
echo ""
echo " To create admin user:"
echo "   oc exec deployment/backend -n $NAMESPACE -- \\"
echo "     python manage_users.py create --username admin --role admin --name 'Administrator'"
echo ""
