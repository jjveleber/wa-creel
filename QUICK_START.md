# Quick Start - Deploy in 5 Minutes

## What You Have

✅ **All deployment files ready in `/mnt/user-data/outputs/`**

## Required Files for GitHub

Copy these files to your new GitHub repo:

### Core Files (REQUIRED):
- `index.py` - Web server + dashboard
- `main.py` - Data collector
- `requirements.txt` - Python dependencies
- `app.yaml` - Google Cloud configuration

### Deployment Helpers (RECOMMENDED):
- `.gitignore` - Excludes unnecessary files from git
- `.gcloudignore` - Excludes unnecessary files from deployment
- `README.md` - Project documentation
- `DEPLOYMENT.md` - Detailed deployment guide
- `deploy.sh` - One-command deployment script

## Step-by-Step

### 1. Create GitHub Repository

Go to https://github.com/new and create `wdfw-creel-dashboard`

### 2. Upload Files

**Option A: Via GitHub Web Interface**
- Drag and drop all files from outputs folder
- Commit directly to main branch

**Option B: Via Command Line**
```bash
# Navigate to outputs folder
cd /mnt/user-data/outputs

# Initialize git
git init
git add .
git commit -m "Initial commit - WDFW Creel Dashboard"

# Connect to GitHub
git remote add origin https://github.com/jjveleber/wa-creel.git
git branch -M main
git push -u origin main
```

### 3. Deploy to Google Cloud

```bash
# Make sure you're in the project directory
cd wdfw-creel-dashboard

# Login to Google Cloud (if not already)
gcloud auth login

# Set/create project
gcloud config set project YOUR_PROJECT_ID

# Create App Engine app (first time only)
gcloud app create --region=us-west2

# Deploy!
./deploy.sh
# or manually: gcloud app deploy
```

### 4. Open Your Dashboard

```bash
gcloud app browse
```

## What Happens on First Load

1. ⏳ **Initial data collection** (1-2 minutes)
   - Fetches 13 years of WDFW data
   - Creates SQLite database
   - Stores in `wdfw_creel_data/` folder

2. 🎨 **Dashboard loads**
   - Interactive map with marine areas
   - Charts and filters
   - Ready to use!

3. 🔄 **Auto-updates**
   - Checks for new data every 24 hours
   - Updates automatically in background

## Cost

- **Free tier**: 28 instance hours/day
- **Light usage**: FREE
- **App scales to zero** when not in use
- Estimate: $0-5/month for typical usage

## Troubleshooting

**"App already exists" error:**
- App Engine can only be created once per project
- Just run: `gcloud app deploy`

**First load is slow:**
- Normal! Data collection takes 1-2 minutes
- Subsequent loads are fast

**Need help?**
- Check `DEPLOYMENT.md` for detailed guide
- View logs: `gcloud app logs tail -s default`

## Next Steps

After deployment:
- ⭐ Star your repo on GitHub
- 📝 Update README.md with your app URL
- 🔗 Share with colleagues
- 📊 Monitor usage in Google Cloud Console

## Files You're Deploying

```
wdfw-creel-dashboard/
├── index.py              # 61KB - Web server
├── main.py               # 22KB - Data collector  
├── requirements.txt      # Minimal dependencies
├── app.yaml             # App Engine config
├── deploy.sh            # Deployment script
├── README.md            # Documentation
└── DEPLOYMENT.md        # Detailed guide
```

---

**Ready to deploy?** Just follow the 3 steps above! 🚀
