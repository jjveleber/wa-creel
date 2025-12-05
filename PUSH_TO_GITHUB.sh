#!/bin/bash
# Script to push files to GitHub

set -e

echo "📦 Pushing wa-creel to GitHub..."
echo ""

# Check if git is installed
if ! command -v git &> /dev/null; then
    echo "❌ Error: git is not installed"
    exit 1
fi

# Initialize git if not already
if [ ! -d .git ]; then
    echo "📝 Initializing git repository..."
    git init
    git branch -M main
fi

# Add all files
echo "➕ Adding files..."
git add .

# Commit
echo "💾 Committing..."
git commit -m "Initial commit - WDFW Creel Dashboard

Features:
- Interactive map with WDFW GIS marine areas
- Multi-select area filtering (toggle on map click)
- Real-time charts and visualizations
- Automatic data updates every 24 hours
- Instant filter application
- SQLite database with 13 years of creel data"

# Add remote (will fail if already exists, that's OK)
echo "🔗 Adding GitHub remote..."
git remote add origin https://github.com/jjveleber/wa-creel.git 2>/dev/null || true

# Push
echo "⬆️ Pushing to GitHub..."
git push -u origin main --force

echo ""
echo "✅ Successfully pushed to https://github.com/jjveleber/wa-creel"
echo ""
echo "🚀 Next step: Deploy to Google Cloud"
echo "   cd wa-creel"
echo "   ./deploy.sh"
