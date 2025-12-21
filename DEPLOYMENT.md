# WDFW Creel Dashboard - Cloud Run Deployment Guide

## 🚀 Quick Deploy

### Prerequisites
- Google Cloud Project with Cloud Run enabled
- GCS bucket for database: `gs://YOUR-PROJECT-ID-wa-creel-data`

### Deploy with Cloud Build
```bash
# Update cloudbuild.yaml with your GCS bucket name
# Then:
gcloud builds submit --config cloudbuild.yaml
```

### Deploy with gcloud
```bash
gcloud builds submit --tag gcr.io/YOUR-PROJECT-ID/wa-creel
gcloud run deploy wa-creel \
  --image gcr.io/YOUR-PROJECT-ID/wa-creel \
  --region us-west1 \
  --platform managed \
  --allow-unauthenticated \
  --memory 512Mi \
  --cpu 1 \
  --set-env-vars GCS_BUCKET_NAME=YOUR-BUCKET-NAME
```

## 📁 Production Structure
```
wa-creel/
├── app/              # Core application
├── static/           # Frontend assets
├── docs/             # Documentation
├── run.py            # Server entry point
├── data_collector.py # Data fetching
├── Dockerfile        # Container definition
├── cloudbuild.yaml   # Cloud Build config
└── .dockerignore     # Docker exclusions
```

## 🔧 Configuration

### Environment Variables
- `GCS_BUCKET_NAME` (required) - Google Cloud Storage bucket
- `PORT` (optional) - Defaults to 8080

### Cloud Run Settings
- Memory: 512Mi
- CPU: 1 vCPU with boost
- Max instances: 2
- Min instances: 0
- Timeout: 300s
- Region: us-west1

## ✅ Post-Deployment

```bash
# Check status
gcloud run services describe wa-creel --region us-west1

# View logs
gcloud run logs read wa-creel --region us-west1 --limit 50

# Get URL
gcloud run services describe wa-creel --region us-west1 --format="value(status.url)"
```

## 🐛 Troubleshooting

### View build logs
```bash
gcloud builds list --limit=5
gcloud builds log BUILD_ID
```

### Check service
```bash
gcloud run services list
gcloud run revisions list --service wa-creel --region us-west1
```

## 🔗 Resources
- Live site: https://wa-creel.jeremyveleber.com
- WDFW Data: https://wdfw.wa.gov/fishing/reports/creel/puget-annual/
