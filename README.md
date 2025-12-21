# WDFW Creel Dashboard - Refactored

Professional, maintainable web application for visualizing Washington State Department of Fish and Wildlife creel survey data.

## 🎯 Project Structure

```
wa-creel/
├── app/                      # Application package
│   ├── __init__.py          # Package initialization
│   ├── config.py            # Configuration management
│   ├── database.py          # Database operations
│   ├── gcs_storage.py       # Google Cloud Storage integration
│   └── server.py            # HTTP server & request handlers
├── static/                   # Static files
│   ├── index.html           # Main HTML template
│   ├── css/
│   │   └── styles.css       # Application styles
│   └── js/
│       ├── app.js           # Main application logic
│       └── custom-areas.js  # Custom marine area polygons
├── data_collector.py         # WDFW data collection script
├── run.py                    # Application entry point
├── requirements.txt          # Python dependencies
├── Dockerfile                # Container configuration
├── cloudbuild.yaml           # Cloud Build configuration
└── .gitignore               # Git ignore rules
```

## 🚀 Quick Start

### Local Development

1. **Create virtual environment:**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate  # Linux/Mac
   # or
   .venv\Scripts\activate  # Windows
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Collect data:**
   ```bash
   python data_collector.py
   ```

4. **Run server:**
   ```bash
   python run.py
   ```

5. **Open browser:**
   ```
   http://localhost:8080
   ```

### Cloud Run Deployment

The application automatically deploys to Google Cloud Run when you push to the main branch.

**Live URL:** https://wa-creel.jeremyveleber.com

## 📁 Module Descriptions

### `app/config.py`
- Centralized configuration management
- Environment variable handling
- Server, database, and GCS settings

### `app/database.py`
- SQLite database operations
- Query functions for statistics, areas, and filtered data
- Metadata management (last update tracking)

### `app/gcs_storage.py`
- Google Cloud Storage integration
- Database persistence across deployments
- Upload/download operations

### `app/server.py`
- HTTP request handling
- REST API endpoints:
  - `/api/stats` - Overall statistics
  - `/api/areas` - Catch areas list
  - `/api/data` - Filtered creel records
  - `/api/update` - Trigger data update
- Static file serving

### `data_collector.py`
- Fetches data from WDFW APIs
- Stores in SQLite database
- Handles 13 years of creel survey data

### `run.py`
- Application entry point
- Initializes server
- Handles startup tasks (GCS download, etc.)

## 🎨 Features

- **Interactive Map** - Leaflet-based map with WDFW marine areas
- **Custom Polygons** - 8 hand-traced marine areas:
  - Bellingham Bay
  - Commencement Bay
  - Dungeness Bay
  - Hoodsport Hatchery
  - Inner Elliott Bay Fishery Area
  - Quilcene/Dabob Bay
  - Sinclair Inlet
  - Tulalip Terminal Area
- **Dynamic Filtering** - Year, area, species, month filters
- **Data Visualization** - Chart.js powered charts
- **Auto-updates** - 24-hour automatic data refresh
- **Database Persistence** - GCS-backed SQLite database

## 🔧 Configuration

### Environment Variables

- `PORT` - Server port (default: 8080)
- `GCS_BUCKET_NAME` - Google Cloud Storage bucket for database persistence

### Cloud Run Settings

Set in `cloudbuild.yaml`:
- Region: `us-west1`
- Memory: `512Mi`
- CPU: `1`
- Max instances: `2`
- Timeout: `300s`

## 📊 Database Schema

**creel_records** table:
- survey_year
- survey_month
- catch_area
- species
- total_catch
- (other WDFW survey fields)

**metadata** table:
- key
- value
- updated_at

## 🧪 Testing Locally

```bash
# Test data collection
python data_collector.py

# Test server
python run.py

# Visit http://localhost:8080
# Test API endpoints:
curl http://localhost:8080/api/stats
curl http://localhost:8080/api/areas
```

## 🚢 Deployment

### Automatic (GitHub → Cloud Run)

1. Push to main branch
2. Cloud Build automatically:
   - Builds Docker image
   - Pushes to Container Registry
   - Deploys to Cloud Run

### Manual

```bash
gcloud builds submit --config cloudbuild.yaml
```

## 🗄️ Database Persistence

Database is stored in Google Cloud Storage bucket:
- **Bucket**: `wa-creel-969186987830-wa-creel-data`
- **File**: `creel_data.db`
- **Lifecycle**: Downloads on startup, uploads after updates

## 📝 Code Quality

### Benefits of Refactoring

- ✅ **Modular** - Each file has a single responsibility
- ✅ **Testable** - Functions can be unit tested
- ✅ **Maintainable** - Easy to find and modify code
- ✅ **Scalable** - Simple to add new features
- ✅ **Professional** - Industry-standard structure

### File Sizes (Before → After)

- `index.py`: 2464 lines → **eliminated**
- `app/server.py`: **300 lines**
- `app/database.py`: **113 lines**
- `app/gcs_storage.py`: **60 lines**
- `app/config.py`: **30 lines**
- `static/js/app.js`: **1491 lines** (extracted from index.py)
- `static/css/styles.css`: **141 lines** (extracted from index.py)

## 🤝 Contributing

1. Create feature branch
2. Make changes
3. Test locally
4. Push and create pull request

## 📜 License

Built for analyzing Washington State Department of Fish and Wildlife public creel survey data.

## 🔗 Links

- **Live App**: https://wa-creel.jeremyveleber.com
- **GitHub**: https://github.com/jjveleber/wa-creel
- **WDFW Data Source**: https://wdfw.wa.gov/fishing/management/creel-surveys

## 👨‍💻 Author

Jeremy Veleber

---

Built with Python, Leaflet, Chart.js, and Google Cloud Run
