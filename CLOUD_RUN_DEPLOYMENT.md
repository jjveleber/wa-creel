# Cloud Run Deployment Guide

## Overview

This app deploys to **Google Cloud Run** using a Dockerfile and automatic GitHub deployments.

## Files for Cloud Run

- ✅ **Dockerfile** - Container definition
- ✅ **cloudbuild.yaml** - Build & deploy pipeline
- ✅ **.dockerignore** - Files to exclude from container
- ✅ **index.py** - Web server
- ✅ **main.py** - Data collector
- ✅ **requirements.txt** - Python dependencies

**Note:** `app.yaml` is for App Engine and is NOT used with Cloud Run.

## Setup (One-Time)

### 1. Enable Required APIs

In Google Cloud Console, enable:
- Cloud Run API
- Cloud Build API
- Container Registry API

Or via command line:
```bash
gcloud services enable run.googleapis.com
gcloud services enable cloudbuild.googleapis.com
gcloud services enable containerregistry.googleapis.com
```

### 2. Grant Cloud Build Permissions

Cloud Build needs permission to deploy to Cloud Run:

**Via Console:**
1. Go to **IAM & Admin → IAM**
2. Find: `[PROJECT_NUMBER]@cloudbuild.gserviceaccount.com`
3. Click **Edit** → **Add Another Role**
4. Add these roles:
   - **Cloud Run Admin**
   - **Service Account User**
   - **Cloud Build Service Account**

**Via Command Line:**
```bash
PROJECT_ID=$(gcloud config get-value project)
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format="value(projectNumber)")

# Cloud Run Admin
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member=serviceAccount:${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com \
  --role=roles/run.admin

# Service Account User
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member=serviceAccount:${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com \
  --role=roles/iam.serviceAccountUser

# Cloud Build Service Account
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member=serviceAccount:${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com \
  --role=roles/cloudbuild.builds.builder
```

### 3. Connect GitHub to Cloud Build

Already done! ✅

## First Deployment

### Option 1: Manual (Recommended First Time)

Use Cloud Shell:

```bash
# Clone repo
git clone https://github.com/jjveleber/wa-creel.git
cd wa-creel

# Build and deploy
gcloud builds submit --config cloudbuild.yaml

# Or use gcloud run deploy directly
gcloud run deploy wa-creel \
  --source . \
  --region=us-west2 \
  --allow-unauthenticated \
  --memory=512Mi \
  --max-instances=2
```

### Option 2: Push to GitHub

Just push `Dockerfile` and updated `cloudbuild.yaml` to main branch.
Cloud Build will automatically:
1. Build the Docker container
2. Push to Container Registry
3. Deploy to Cloud Run

## Automatic Deployments

After setup, every push to `main` branch automatically:
```
Push to GitHub
    ↓
Cloud Build trigger
    ↓
Build Docker image
    ↓
Push to Container Registry
    ↓
Deploy to Cloud Run
    ↓
App is live!
```

## View Your App

After deployment:

**Via Console:**
- Go to **Cloud Run → Services → wa-creel**
- Click the URL at the top

**Via Command Line:**
```bash
gcloud run services describe wa-creel --region=us-west2 --format="value(status.url)"
```

## Configuration

### Update Memory/CPU

Edit `cloudbuild.yaml`:
```yaml
- '--memory=512Mi'    # Change to 256Mi, 1Gi, 2Gi, etc.
- '--cpu=1'           # Change to 2, 4, etc.
- '--max-instances=2' # Change max scaling
```

### Environment Variables

Add to `cloudbuild.yaml` deploy step:
```yaml
- '--set-env-vars=MAX_YEARS=13,UPDATE_INTERVAL=24'
```

Or set via Console:
- Cloud Run → Service → Edit & Deploy New Revision → Environment Variables

## Monitoring

### View Logs
```bash
gcloud run logs tail wa-creel --region=us-west2
```

Or in Console: **Cloud Run → wa-creel → Logs**

### View Metrics

Console: **Cloud Run → wa-creel → Metrics**
- Request count
- Request latency
- Container CPU/Memory usage
- Instance count

## Cost Estimation

Cloud Run Pricing (Free Tier):
- 2 million requests/month free
- 360,000 GB-seconds of memory free
- 180,000 vCPU-seconds free

Estimated costs:
- **Low usage** (100 requests/day): FREE
- **Medium usage** (1000 requests/day): $1-3/month
- **High usage** (10,000 requests/day): $10-20/month

**Scales to zero** when not in use = no charges!

## Database Persistence

**Important:** Cloud Run containers are ephemeral. The SQLite database is recreated on:
- New deployments
- Container restarts
- Auto-scaling events

### Current Behavior:
- First request after restart: Fetches data (~1-2 min)
- Subsequent requests: Uses in-memory database
- Auto-updates every 24 hours

### For Production Persistence:
Consider migrating to Cloud SQL or Cloud Storage if you need:
- Data persistence across restarts
- Faster cold starts
- Multiple container instances sharing data

## Troubleshooting

### Build Fails

**Check Cloud Build logs:**
- Console: Cloud Build → History → Click build
- Command: `gcloud builds list --limit=5`

**Common issues:**
- Missing permissions (see Setup step 2)
- APIs not enabled (see Setup step 1)
- Dockerfile syntax errors

### Container Crashes

**Check Cloud Run logs:**
```bash
gcloud run logs tail wa-creel --region=us-west2
```

**Common issues:**
- Port mismatch (ensure using $PORT environment variable)
- Missing dependencies in requirements.txt
- Database initialization errors

### Slow First Load

Normal! First request after deployment:
- Starts container (cold start)
- Fetches WDFW data (~1-2 minutes)
- Subsequent requests are fast

To reduce:
- Set `--min-instances=1` (keeps one instance warm, costs more)
- Pre-fetch data during build (advanced)

## Manual Deployment

Bypass Cloud Build and deploy directly:

```bash
cd wa-creel

# Deploy from source
gcloud run deploy wa-creel \
  --source . \
  --region=us-west2 \
  --allow-unauthenticated

# Or build locally and deploy
docker build -t gcr.io/PROJECT_ID/wa-creel .
docker push gcr.io/PROJECT_ID/wa-creel
gcloud run deploy wa-creel \
  --image=gcr.io/PROJECT_ID/wa-creel \
  --region=us-west2
```

## Updating Your App

```bash
# Make changes locally
git add .
git commit -m "Update description"
git push origin main

# Cloud Build automatically deploys!
# Watch progress: Cloud Build → History
```

## Delete Service

To remove the Cloud Run service:

```bash
gcloud run services delete wa-creel --region=us-west2
```

Or in Console: Cloud Run → wa-creel → Delete

## Differences from App Engine

| Feature | App Engine | Cloud Run |
|---------|------------|-----------|
| Configuration | app.yaml | Dockerfile + cloudbuild.yaml |
| Scaling | Slower | Faster (to zero instantly) |
| Cold starts | Slower | Faster |
| Cost | Pay per instance hour | Pay per request |
| Best for | Always-on apps | Bursty traffic |

Cloud Run is better for this app because:
- ✅ Better scaling to zero (lower cost)
- ✅ Faster cold starts
- ✅ Pay only for actual usage
- ✅ More consistent with wave-safe

## Next Steps

1. ✅ Upload Dockerfile to GitHub
2. ✅ Upload updated cloudbuild.yaml to GitHub  
3. ✅ Upload .dockerignore to GitHub
4. Run first deployment (see above)
5. Test automatic deployments by making a small change
