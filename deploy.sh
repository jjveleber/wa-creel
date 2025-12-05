#!/bin/bash
# Simple deployment script for Google Cloud App Engine

set -e

echo "🚀 Deploying WDFW Creel Dashboard to Google Cloud..."
echo ""

# Check if gcloud is installed
if ! command -v gcloud &> /dev/null; then
    echo "❌ Error: gcloud CLI is not installed"
    echo "Install from: https://cloud.google.com/sdk/docs/install"
    exit 1
fi

# Check if logged in
if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" &> /dev/null; then
    echo "❌ Error: Not logged in to gcloud"
    echo "Run: gcloud auth login"
    exit 1
fi

# Get current project
PROJECT=$(gcloud config get-value project 2>/dev/null)
if [ -z "$PROJECT" ]; then
    echo "❌ Error: No project set"
    echo "Run: gcloud config set project YOUR_PROJECT_ID"
    exit 1
fi

echo "📦 Project: $PROJECT"
echo ""

# Deploy
echo "⏳ Deploying to App Engine..."
gcloud app deploy --quiet

echo ""
echo "✅ Deployment complete!"
echo ""
echo "🌐 Your app is live at:"
gcloud app browse --no-launch-browser 2>/dev/null || echo "   Run 'gcloud app browse' to get URL"
echo ""
echo "📊 View logs:"
echo "   gcloud app logs tail -s default"
