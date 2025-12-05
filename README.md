# WDFW Puget Sound Creel Data Dashboard

Interactive dashboard for visualizing Washington State Department of Fish and Wildlife (WDFW) saltwater fishing survey data.

## Features

- 🗺️ **Interactive Map**: Click marine areas to filter data with WDFW GIS integration
- 📊 **Real-time Charts**: Trend analysis, species breakdown, top areas, monthly distribution
- 🔄 **Auto-Updates**: Automatically checks for new data every 24 hours
- 🎯 **Multi-Select Filters**: Year range, catch areas, species, time granularity
- ⚡ **Instant Filtering**: All filters apply immediately

## Tech Stack

- **Backend**: Python 3.9+ with built-in HTTP server
- **Database**: SQLite
- **Frontend**: Vanilla JavaScript with Chart.js and Leaflet
- **Data Source**: WDFW Creel Survey CSV exports
- **GIS**: Esri Leaflet for marine area polygons

## Local Development

### Prerequisites

- Python 3.9+
- pip

### Setup

1. Clone the repository:
```bash
git clone https://github.com/jjveleber/wa-creel.git
cd wdfw-creel-dashboard
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Run the data collector (first time only):
```bash
python main.py
```
This will create `wdfw_creel_data/` directory and fetch data from WDFW.

4. Start the server:
```bash
python index.py
```

5. Open your browser:
```
http://localhost:8080
```

## Deployment to Google Cloud Run

### Prerequisites

- Google Cloud account
- Cloud Build connected to GitHub (automatic deployments)
- Cloud Run, Cloud Build, and Container Registry APIs enabled

### Deploy

**Automatic (Recommended):**
Just push to GitHub `main` branch - Cloud Build automatically deploys!

**Manual:**
```bash
# Clone repo
git clone https://github.com/jjveleber/wa-creel.git
cd wa-creel

# Deploy to Cloud Run
gcloud run deploy wa-creel \
  --source . \
  --region=us-west2 \
  --allow-unauthenticated
```

**Get your URL:**
```bash
gcloud run services describe wa-creel --region=us-west2 --format="value(status.url)"
```

### First Deployment Notes

- The first page load will fetch data from WDFW (may take 1-2 minutes)
- Subsequent loads are instant
- Data automatically updates every 24 hours
- **Scales to zero** when not in use (lower cost!)

See [CLOUD_RUN_DEPLOYMENT.md](CLOUD_RUN_DEPLOYMENT.md) for detailed setup.

## Project Structure

```
wa-creel/
├── index.py              # Web server + embedded dashboard
├── main.py               # Data collection from WDFW
├── requirements.txt      # Python dependencies
├── Dockerfile            # Container definition for Cloud Run
├── cloudbuild.yaml       # Cloud Build configuration
├── .dockerignore         # Files to exclude from container
├── .gcloudignore         # Files to exclude from deployment
├── .gitignore            # Files to exclude from git
└── wdfw_creel_data/      # SQLite database (created at runtime)
    ├── creel_data.db     # Main data table
    └── .last_update      # Update timestamp
```

## API Endpoints

- `GET /` - Dashboard HTML
- `GET /api/stats` - Overall statistics
- `GET /api/trend` - Time series data
- `GET /api/species` - Species totals
- `GET /api/areas` - Top catch areas
- `GET /api/monthly` - Monthly distribution
- `GET /api/map_data` - Data for map visualization
- `GET /api/filter_options` - Available filter options
- `GET /api/update` - Check/trigger data update

## Data Source

Data is collected from WDFW's public creel survey reports:
https://wdfw.wa.gov/fishing/reports/creel/

The dashboard fetches the last 13 years of data and stores it in SQLite for fast querying.

## License

MIT

## Author

Jeremy Veleber
