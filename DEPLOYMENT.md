# Deployment Guide

## Quick Start (5 minutes)

### 1. Create GitHub Repository

```bash
# Create new repo on GitHub (via web interface)
# Then locally:
cd wa-creel
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/wa-creel.git
git push -u origin main
```

### 2. Set Up Google Cloud

#### First Time Setup:

```bash
# Install gcloud CLI (if not installed)
# https://cloud.google.com/sdk/docs/install

# Login to Google Cloud
gcloud auth login

# Create a new project (or use existing)
gcloud projects create wa-creel --name="WDFW Creel Dashboard"

# Set the project
gcloud config set project wa-creel

# Enable App Engine
gcloud app create --region=us-west2
```

### 3. Deploy

```bash
# Option 1: Use the deployment script
./deploy.sh

# Option 2: Manual deployment
gcloud app deploy
```

### 4. Open Your App

```bash
gcloud app browse
```

## Configuration

### app.yaml Settings

Current configuration:
- **Runtime**: Python 3.9
- **Instance Class**: F2 (512MB RAM, 1.2GHz CPU)
- **Scaling**: 0-2 instances
- **Entry Point**: `python index.py`

To adjust resources, edit `app.yaml`:

```yaml
instance_class: F1  # Smaller (cheaper)
instance_class: F2  # Default
instance_class: F4  # Larger (more expensive)
```

### Environment Variables

To add environment variables, update `app.yaml`:

```yaml
env_variables:
  MAX_YEARS: "13"
  UPDATE_INTERVAL_HOURS: "24"
```

## Database Persistence

**Important:** App Engine has an ephemeral filesystem. The SQLite database is recreated on each deployment.

### Options:

1. **Current Setup (Acceptable for this use case)**:
   - Database rebuilds on first request after deployment
   - Takes 1-2 minutes on first load
   - Auto-updates every 24 hours
   - Free and simple

2. **Cloud SQL (For production)**:
   - Persistent database
   - Requires paid Cloud SQL instance
   - Modify code to use PostgreSQL/MySQL

3. **Cloud Storage (Middle ground)**:
   - Store SQLite file in Cloud Storage bucket
   - Download on startup
   - Requires code modifications

## Cost Estimation

### Free Tier Includes:
- 28 instance hours/day
- 1GB outbound data/day
- App Engine scaling to 0 when not in use

### Estimated Monthly Cost:
- **Light usage** (< 100 visits/day): FREE
- **Medium usage** (500 visits/day): $5-10/month
- **Heavy usage** (5000 visits/day): $50-100/month

### To Minimize Costs:

1. Set max_instances to 1 in app.yaml
2. Use min_instances: 0 (current setting)
3. Monitor usage in Cloud Console

## Monitoring

### View Logs:

```bash
# Stream live logs
gcloud app logs tail -s default

# View recent logs
gcloud app logs read --limit 100
```

### View Metrics:

```bash
# Open Cloud Console
gcloud app open-console
```

## Troubleshooting

### Deployment Fails

**Error: "App already exists"**
```bash
# App Engine already initialized, just deploy
gcloud app deploy
```

**Error: "Permission denied"**
```bash
# Re-authenticate
gcloud auth login
```

### App Not Loading

1. Check logs:
```bash
gcloud app logs tail -s default
```

2. Common issues:
   - First load takes 1-2 minutes (data collection)
   - Check quota limits in Cloud Console
   - Verify main.py is deployed

### Database Issues

If data isn't updating:
1. Check logs for update errors
2. Verify WDFW API is accessible
3. Check metadata table in database

## Updating Your App

```bash
# Make changes locally
git add .
git commit -m "Update description"
git push origin main

# Deploy to Google Cloud
gcloud app deploy
```

## Custom Domain

To use your own domain:

1. Verify domain ownership in Cloud Console
2. Map custom domain:
```bash
gcloud app domain-mappings create www.yourdomain.com
```
3. Update DNS records as instructed

## Rollback

To revert to previous version:

```bash
# List versions
gcloud app versions list

# Route traffic to specific version
gcloud app versions migrate VERSION_ID
```

## Delete App

To completely remove the app:

```bash
# Delete all versions
gcloud app versions delete VERSION_ID

# Note: Cannot delete App Engine once created
# Can only disable it in Cloud Console
```

## Support

For issues:
1. Check logs first
2. Review Cloud Console error reporting
3. Check GitHub issues
