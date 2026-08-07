#!/bin/bash
set -euo pipefail

# ============================================================
# OpenShift Deploy Script for Logistics System
# ============================================================

NAMESPACE="logistics"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "============================================"
echo " Logistics System - OpenShift Deployment"
echo "============================================"

# Check oc command
if ! command -v oc &> /dev/null; then
    echo "ERROR: 'oc' command not found. Please install OpenShift CLI."
    exit 1
fi

# Check if logged in
if ! oc whoami &> /dev/null; then
    echo "ERROR: Not logged in to OpenShift. Run 'oc login' first."
    exit 1
fi

echo ""
echo "[1/8] Creating namespace..."
oc apply -f "$SCRIPT_DIR/00-namespace.yaml"

echo "[2/8] Applying secrets (edit before deploying!)..."
oc apply -f "$SCRIPT_DIR/01-secrets.yaml"

echo "[3/8] Applying configmap..."
oc apply -f "$SCRIPT_DIR/02-configmap.yaml"

echo "[4/8] Deploying PostgreSQL..."
oc apply -f "$SCRIPT_DIR/03-postgresql.yaml"

echo "[5/8] Deploying Redis..."
oc apply -f "$SCRIPT_DIR/04-redis.yaml"

echo "[6/8] Deploying Backend..."
oc apply -f "$SCRIPT_DIR/05-backend.yaml"

echo "[7/8] Deploying Celery Worker..."
oc apply -f "$SCRIPT_DIR/06-celery-worker.yaml"

echo "[8/8] Deploying Frontend + Route..."
oc apply -f "$SCRIPT_DIR/07-frontend.yaml"

echo ""
echo "============================================"
echo " Deployment Complete!"
echo "============================================"
echo ""
echo " IMPORTANT: Before the system works, you need to:"
echo ""
echo " 1. Edit secrets:"
echo "    oc edit secret logistics-secrets -n $NAMESPACE"
echo ""
echo " 2. Update BuildConfig git URL:"
echo "    oc edit bc backend -n $NAMESPACE"
echo "    oc edit bc frontend -n $NAMESPACE"
echo ""
echo " 3. Start builds:"
echo "    oc start-build backend -n $NAMESPACE"
echo "    oc start-build frontend -n $NAMESPACE"
echo ""
echo " 4. Create admin user:"
echo "    oc exec deployment/backend -n $NAMESPACE -- \\"
echo "      python manage_users.py create --username admin --role admin --name 'Administrator'"
echo ""
echo " 5. Get route URL:"
echo "    oc get route frontend -n $NAMESPACE -o jsonpath='{.spec.host}'"
echo ""
