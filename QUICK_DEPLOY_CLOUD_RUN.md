# Quick Deploy to Cloud Run

## 1. Upload New Files to GitHub

Upload these 3 files to https://github.com/jjveleber/wa-creel:

- ✅ **Dockerfile** (new)
- ✅ **cloudbuild.yaml** (updated for Cloud Run)
- ✅ **.dockerignore** (new)

**You can delete:** app.yaml (not needed for Cloud Run)

## 2. Grant Permissions (One-Time)

In Google Cloud Console:

**IAM & Admin → IAM** → Find `[PROJECT_NUMBER]@cloudbuild.gserviceaccount.com` → Edit

Add these 3 roles:
- ✅ Cloud Run Admin
- ✅ Service Account User  
- ✅ Cloud Build Service Account

## 3. Enable APIs (One-Time)

**APIs & Services → Enable APIs and Services**

Search and enable:
- ✅ Cloud Run API
- ✅ Cloud Build API
- ✅ Container Registry API

## 4. Deploy!

### Option A: Let Cloud Build Auto-Deploy

Just push the new files to GitHub main branch. Done! ✨

Check progress: **Cloud Build → History**

### Option B: Manual First Deploy

**Cloud Shell:**
```bash
git clone https://github.com/jjveleber/wa-creel.git
cd wa-creel
gcloud run deploy wa-creel \
  --source . \
  --region=us-west2 \
  --allow-unauthenticated
```

## 5. Get Your URL

**Cloud Run → Services → wa-creel** → Click the URL

Or:
```bash
gcloud run services describe wa-creel --region=us-west2 --format="value(status.url)"
```

## That's It!

Every push to `main` branch automatically deploys to Cloud Run. 🚀

**Note:** First load takes 1-2 minutes (fetching WDFW data). Subsequent loads are instant.

## Cost

Cloud Run free tier:
- 2 million requests/month FREE
- Scales to zero when not in use
- Estimated: $0-5/month for typical usage

## Differences from App Engine Setup

| Old (App Engine) | New (Cloud Run) |
|------------------|-----------------|
| app.yaml | Dockerfile |
| Slower scaling | Instant scaling to zero |
| $5-10/month minimum | $0-5/month |
| 1-2 min cold start | Faster cold starts |

Cloud Run is better for this app! ✨
