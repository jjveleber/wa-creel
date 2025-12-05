#!/usr/bin/env python3
"""
Simple web server for the WDFW Creel Dashboard
Serves data from SQLite database via HTTP endpoints
"""

from http.server import HTTPServer, SimpleHTTPRequestHandler
import json
import sqlite3
import os
from urllib.parse import urlparse, parse_qs
from datetime import datetime, timedelta
import sys

# Import Google Cloud Storage
try:
    from google.cloud import storage
    GCS_AVAILABLE = True
except ImportError:
    GCS_AVAILABLE = False
    print("Warning: google-cloud-storage not installed. Database persistence disabled.")

# Import the data collector
try:
    from main import WDFWCreelCollector
except ImportError:
    WDFWCreelCollector = None
    print("Warning: Could not import WDFWCreelCollector from main.py")


# Google Cloud Storage helper functions
def download_database_from_gcs(bucket_name, db_path):
    """Download database from Google Cloud Storage if it exists"""
    if not GCS_AVAILABLE:
        return False
    
    try:
        # Ensure data directory exists
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        
        storage_client = storage.Client()
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob("creel_data.db")
        
        if blob.exists():
            print(f"📥 Downloading database from gs://{bucket_name}/creel_data.db")
            blob.download_to_filename(db_path)
            print(f"✅ Database downloaded successfully")
            return True
        else:
            print(f"ℹ️  No existing database found in GCS bucket")
            return False
    except Exception as e:
        print(f"⚠️  Could not download database from GCS: {e}")
        return False


def upload_database_to_gcs(bucket_name, db_path):
    """Upload database to Google Cloud Storage"""
    if not GCS_AVAILABLE:
        return False
    
    if not os.path.exists(db_path):
        print(f"⚠️  Database file not found at {db_path}, skipping upload")
        return False
    
    try:
        storage_client = storage.Client()
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob("creel_data.db")
        
        print(f"📤 Uploading database to gs://{bucket_name}/creel_data.db")
        blob.upload_from_filename(db_path)
        print(f"✅ Database uploaded successfully")
        return True
    except Exception as e:
        print(f"⚠️  Could not upload database to GCS: {e}")
        return False



class CreelDataHandler(SimpleHTTPRequestHandler):
    DB_PATH = os.path.join("wdfw_creel_data", "creel_data.db")

    def do_GET(self):
        parsed_path = urlparse(self.path)
        query_params = parse_qs(parsed_path.query)

        # Serve the dashboard HTML at root
        if parsed_path.path == '/':
            self.serve_dashboard()
        # API endpoints for data
        elif parsed_path.path == '/api/stats':
            self.serve_stats(query_params)
        elif parsed_path.path == '/api/yearly':
            self.serve_yearly_data(query_params)
        elif parsed_path.path == '/api/trend':
            self.serve_trend_data(query_params)
        elif parsed_path.path == '/api/species':
            self.serve_species_totals(query_params)
        elif parsed_path.path == '/api/areas':
            self.serve_top_areas(query_params)
        elif parsed_path.path == '/api/monthly':
            self.serve_monthly_data(query_params)
        elif parsed_path.path == '/api/map_data':
            self.serve_map_data(query_params)
        elif parsed_path.path == '/api/filter_options':
            self.serve_filter_options()
        elif parsed_path.path == '/api/update':
            self.serve_update_data()
        else:
            self.send_error(404, "Not Found")

    def get_db_connection(self):
        """Get database connection"""
        if not os.path.exists(self.DB_PATH):
            raise FileNotFoundError(f"Database not found at {self.DB_PATH}")
        return sqlite3.connect(self.DB_PATH)

    def build_where_clause(self, params):
        """Build WHERE clause from query parameters"""
        conditions = []
        query_params = []

        # Year range filter
        if 'year_start' in params:
            year_start = params['year_start'][0]
            conditions.append("substr(sample_date, -4) >= ?")
            query_params.append(year_start)

        if 'year_end' in params:
            year_end = params['year_end'][0]
            conditions.append("substr(sample_date, -4) <= ?")
            query_params.append(year_end)

        # Catch area filter (multi-select)
        if 'catch_area' in params:
            areas = [a for a in params['catch_area'] if a]
            if areas:
                placeholders = ','.join(['?'] * len(areas))
                conditions.append(f"catch_area IN ({placeholders})")
                query_params.extend(areas)

        # Build WHERE clause
        if conditions:
            where_clause = " WHERE " + " AND ".join(conditions)
        else:
            where_clause = ""

        return where_clause, query_params

    def get_species_columns(self, params):
        """Get species columns to aggregate based on filter"""
        if 'species' not in params:
            return "chinook + coho + chum + pink + sockeye"

        species_list = [s for s in params['species'] if s and s != 'all']

        if not species_list or 'all' in params.get('species', []):
            # Return all salmon species
            return "chinook + coho + chum + pink + sockeye"
        else:
            # Return sum of selected species
            return ' + '.join([s.lower() for s in species_list])

    def get_species_list(self, params):
        """Get list of species for trend chart"""
        if 'species' not in params:
            return ['chinook', 'coho', 'chum', 'pink', 'sockeye']

        species_list = [s for s in params['species'] if s and s != 'all']

        if not species_list or 'all' in params.get('species', []):
            return ['chinook', 'coho', 'chum', 'pink', 'sockeye']
        else:
            return [s.lower() for s in species_list]

    def send_json(self, data):
        """Send JSON response"""
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def serve_dashboard(self):
        """Serve the dashboard HTML"""
        html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>WDFW Puget Sound Creel Data Dashboard</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/3.9.1/chart.min.js"></script>
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
        integrity="sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY="
        crossorigin=""/>
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"
        integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo="
        crossorigin=""></script>
    <!-- Esri Leaflet for loading WDFW GIS data -->
    <script src="https://unpkg.com/esri-leaflet@2.5.3/dist/esri-leaflet.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        .container { max-width: 1400px; margin: 0 auto; }
        header {
            background: white;
            padding: 30px;
            border-radius: 12px;
            margin-bottom: 20px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        h1 { color: #2d3748; font-size: 2em; margin-bottom: 10px; }
        .subtitle { color: #718096; font-size: 1.1em; }
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-bottom: 20px;
        }
        .stat-card {
            background: white;
            padding: 20px;
            border-radius: 12px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        .stat-value {
            font-size: 2em;
            font-weight: bold;
            color: #667eea;
            margin-bottom: 5px;
        }
        .stat-label { color: #718096; font-size: 0.9em; }
        .charts-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(500px, 1fr));
            gap: 20px;
            margin-bottom: 20px;
        }
        .chart-container {
            background: white;
            padding: 25px;
            border-radius: 12px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        .chart-container.full-width { grid-column: 1 / -1; }
        .chart-title {
            font-size: 1.3em;
            color: #2d3748;
            margin-bottom: 15px;
            font-weight: 600;
        }
        canvas { max-height: 400px; }
        .loading {
            text-align: center;
            padding: 40px;
            color: white;
            font-size: 1.5em;
        }
        .error {
            background: #fc8181;
            color: white;
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 20px;
            display: none;
        }
        .filters {
            background: white;
            padding: 25px;
            border-radius: 12px;
            margin-bottom: 20px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        .filters h2 {
            color: #2d3748;
            font-size: 1.3em;
            margin-bottom: 15px;
        }
        .filter-group {
            display: flex;
            gap: 20px;
            flex-wrap: wrap;
            align-items: flex-end;
        }
        .filter-item {
            flex: 1;
            min-width: 200px;
        }
        .filter-item label {
            display: block;
            margin-bottom: 8px;
            color: #2d3748;
            font-weight: 600;
            font-size: 0.9em;
        }
        .filter-item select {
            width: 100%;
            padding: 10px 12px;
            border: 2px solid #e2e8f0;
            border-radius: 6px;
            font-size: 1em;
            background: white;
            cursor: pointer;
        }
        .filter-item select[multiple] {
            min-height: 120px;
        }
        .filter-item select:focus {
            outline: none;
            border-color: #667eea;
        }
        .filter-buttons {
            display: flex;
            gap: 10px;
        }
        .btn {
            padding: 10px 20px;
            border: none;
            border-radius: 6px;
            font-size: 1em;
            cursor: pointer;
            transition: background 0.3s;
        }
        .btn-primary {
            background: #667eea;
            color: white;
        }
        .btn-primary:hover {
            background: #5568d3;
        }
        .btn-secondary {
            background: #e2e8f0;
            color: #2d3748;
        }
        .btn-secondary:hover {
            background: #cbd5e0;
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🎣 WDFW Puget Sound Creel Data Dashboard</h1>
            <p class="subtitle">Interactive visualization of saltwater fishing survey data</p>
        </header>

        <div class="loading" id="loading">Loading data from database...</div>
        <div class="error" id="error"></div>

        <div id="dashboard" style="display: none;">
            <div class="filters">
                <h2>🔍 Filters</h2>
                <div class="filter-group">
                    <div class="filter-item">
                        <label for="yearStart">Start Year</label>
                        <select id="yearStart" onchange="applyFilters()">
                            <option value="">All Years</option>
                        </select>
                    </div>
                    <div class="filter-item">
                        <label for="yearEnd">End Year</label>
                        <select id="yearEnd" onchange="applyFilters()">
                            <option value="">All Years</option>
                        </select>
                    </div>
                    <div class="filter-item">
                        <label for="catchArea">Catch Area (multi-select)</label>
                        <select id="catchArea" multiple onchange="applyFilters()">
                        </select>
                    </div>
                    <div class="filter-item">
                        <label for="species">Species (multi-select)</label>
                        <select id="species" multiple onchange="applyFilters()">
                            <option value="chinook" selected>Chinook</option>
                            <option value="coho" selected>Coho</option>
                            <option value="chum" selected>Chum</option>
                            <option value="pink" selected>Pink</option>
                            <option value="sockeye" selected>Sockeye</option>
                            <option value="lingcod">Lingcod</option>
                            <option value="halibut">Halibut</option>
                        </select>
                    </div>
                    <div class="filter-item">
                        <label for="timeUnit">Time Granularity</label>
                        <select id="timeUnit" onchange="applyFilters()">
                            <option value="yearly">Yearly</option>
                            <option value="monthly">Monthly</option>
                            <option value="weekly">Weekly</option>
                            <option value="daily">Daily</option>
                        </select>
                    </div>
                    <div class="filter-buttons">
                        <button class="btn btn-secondary" onclick="resetFilters()">Reset</button>
                    </div>
                </div>
            </div>

            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-value" id="totalRecords">0</div>
                    <div class="stat-label">Total Records</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value" id="totalAnglers">0</div>
                    <div class="stat-label">Total Anglers</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value" id="totalChinook">0</div>
                    <div class="stat-label">Total Chinook</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value" id="totalCoho">0</div>
                    <div class="stat-label">Total Coho</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value" id="yearRange">-</div>
                    <div class="stat-label">Year Range</div>
                </div>
            </div>

            <div class="charts-grid">
                <div class="chart-container full-width map-container">
                    <h3 class="chart-title">Puget Sound Catch Areas Map</h3>
                    <div id="map" style="height: 600px; width: 100%;"></div>
                </div>

                <div class="chart-container full-width">
                    <h3 class="chart-title">Catch Trends Over Time</h3>
                    <canvas id="trendChart"></canvas>
                </div>

                <div class="chart-container">
                    <h3 class="chart-title">Total Catch by Species</h3>
                    <canvas id="speciesChart"></canvas>
                </div>

                <div class="chart-container">
                    <h3 class="chart-title">Top 10 Catch Areas</h3>
                    <canvas id="areaChart"></canvas>
                </div>

                <div class="chart-container full-width">
                    <h3 class="chart-title">Monthly Catch Distribution</h3>
                    <canvas id="monthlyChart"></canvas>
                </div>
            </div>
        </div>
    </div>

    <script>
        let charts = {};
        let map = null;
        let mapLayers = [];
        let marineAreasLayer = null; // Store the Esri feature layer
        let selectedAreaLayers = new Set(); // Track all selected areas
        let initialMapLoadComplete = false; // Prevent zoom reset on pan/zoom
        let currentFilters = { 
            time_unit: 'yearly', 
            species: ['chinook', 'coho', 'chum', 'pink', 'sockeye'],
            catch_area: []
        };

        async function loadFilterOptions() {
            try {
                const options = await fetch('/api/filter_options').then(r => r.json());

                // Populate year dropdowns
                const yearStart = document.getElementById('yearStart');
                const yearEnd = document.getElementById('yearEnd');

                options.years.forEach(year => {
                    const opt1 = document.createElement('option');
                    opt1.value = year;
                    opt1.textContent = year;
                    yearStart.appendChild(opt1);

                    const opt2 = document.createElement('option');
                    opt2.value = year;
                    opt2.textContent = year;
                    yearEnd.appendChild(opt2);
                });

                // Set default to full range
                if (options.years.length > 0) {
                    yearStart.value = options.years[0];
                    yearEnd.value = options.years[options.years.length - 1];
                }

                // Populate catch area dropdown (no "All" option for multi-select)
                const catchArea = document.getElementById('catchArea');
                options.areas.forEach(area => {
                    const opt = document.createElement('option');
                    opt.value = area;
                    opt.textContent = area;
                    catchArea.appendChild(opt);
                });
            } catch (err) {
                console.error('Error loading filter options:', err);
            }
        }

        function buildQueryString() {
            const params = new URLSearchParams();

            if (currentFilters.year_start) {
                params.append('year_start', currentFilters.year_start);
            }
            if (currentFilters.year_end) {
                params.append('year_end', currentFilters.year_end);
            }
            if (currentFilters.catch_area && currentFilters.catch_area.length > 0) {
                currentFilters.catch_area.forEach(area => {
                    params.append('catch_area', area);
                });
            }
            if (currentFilters.species && currentFilters.species.length > 0) {
                currentFilters.species.forEach(species => {
                    params.append('species', species);
                });
            }
            if (currentFilters.time_unit) {
                params.append('time_unit', currentFilters.time_unit);
            }

            return params.toString() ? '?' + params.toString() : '';
        }

        function getSelectValues(select) {
            const result = [];
            const options = select && select.options;
            for (let i = 0; i < options.length; i++) {
                if (options[i].selected) {
                    result.push(options[i].value);
                }
            }
            return result;
        }

        function applyFilters() {
            currentFilters = {
                year_start: document.getElementById('yearStart').value,
                year_end: document.getElementById('yearEnd').value,
                catch_area: getSelectValues(document.getElementById('catchArea')),
                species: getSelectValues(document.getElementById('species')),
                time_unit: document.getElementById('timeUnit').value || 'yearly'
            };
            loadData();
        }

        function resetFilters() {
            document.getElementById('yearStart').selectedIndex = 0;
            document.getElementById('yearEnd').selectedIndex = 0;

            // Reset catch area - deselect all
            const catchAreaSelect = document.getElementById('catchArea');
            for (let i = 0; i < catchAreaSelect.options.length; i++) {
                catchAreaSelect.options[i].selected = false;
            }

            // Reset species - select all salmon by default
            const speciesSelect = document.getElementById('species');
            for (let i = 0; i < speciesSelect.options.length; i++) {
                const val = speciesSelect.options[i].value;
                speciesSelect.options[i].selected = ['chinook', 'coho', 'chum', 'pink', 'sockeye'].includes(val);
            }

            document.getElementById('timeUnit').value = 'yearly';
            currentFilters = { 
                time_unit: 'yearly', 
                species: ['chinook', 'coho', 'chum', 'pink', 'sockeye'],
                catch_area: []
            };
            loadData();
        }

        async function loadData() {
            try {
                const queryString = buildQueryString();
                const [stats, trendData, species, areas, monthly, mapData] = await Promise.all([
                    fetch('/api/stats' + queryString).then(r => r.json()),
                    fetch('/api/trend' + queryString).then(r => r.json()),
                    fetch('/api/species' + queryString).then(r => r.json()),
                    fetch('/api/areas' + queryString).then(r => r.json()),
                    fetch('/api/monthly' + queryString).then(r => r.json()),
                    fetch('/api/map_data' + queryString).then(r => r.json())
                ]);

                document.getElementById('loading').style.display = 'none';
                document.getElementById('dashboard').style.display = 'block';

                updateStats(stats);

                // Create map after dashboard is visible
                setTimeout(() => {
                    createMap(mapData);
                }, 250);

                createTrendChart(trendData);
                createSpeciesChart(species);
                createAreaChart(areas);
                createMonthlyChart(monthly);
            } catch (err) {
                document.getElementById('loading').style.display = 'none';
                document.getElementById('error').style.display = 'block';
                document.getElementById('error').textContent = 'Error loading data: ' + err.message;
            }
        }

        function updateStats(stats) {
            document.getElementById('totalRecords').textContent = stats.total_records.toLocaleString();
            document.getElementById('totalAnglers').textContent = stats.total_anglers.toLocaleString();
            document.getElementById('totalChinook').textContent = Math.round(stats.total_chinook).toLocaleString();
            document.getElementById('totalCoho').textContent = Math.round(stats.total_coho).toLocaleString();
            document.getElementById('yearRange').textContent = `${stats.min_year}-${stats.max_year}`;
        }

        function createMap(data) {
            console.log('Creating map with data:', data);

            // Check if Leaflet is loaded
            if (typeof L === 'undefined') {
                console.error('Leaflet library not loaded!');
                document.getElementById('map').innerHTML = '<div style="padding: 20px; text-align: center; color: #e53e3e;">Error: Leaflet library failed to load. Please refresh the page.</div>';
                return;
            }

            // Check if Esri Leaflet is loaded
            if (typeof L.esri === 'undefined') {
                console.error('Esri Leaflet library not loaded!');
                document.getElementById('map').innerHTML = '<div style="padding: 20px; text-align: center; color: #e53e3e;">Error: Esri Leaflet library required. Please refresh the page.</div>';
                return;
            }

            try {
                // Initialize map if not already created
                if (!map) {
                    console.log('Initializing Leaflet map...');

                    const mapElement = document.getElementById('map');
                    if (!mapElement) {
                        console.error('Map container element not found!');
                        return;
                    }

                    map = L.map('map', {
                        center: [47.5, -122.5],
                        zoom: 8,
                        minZoom: 7
                    });

                    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                        attribution: '© OpenStreetMap contributors',
                        maxZoom: 19
                    }).addTo(map);

                    console.log('Map initialized successfully');
                }

                // Create a map of catch data by area name
                const dataMap = {};
                data.forEach(d => {
                    dataMap[d.area] = d;
                });


                // Find max catch for color scaling
                const maxCatch = Math.max(...data.map(d => d.total), 1);
                console.log('Max catch for color scaling:', maxCatch);


                // Helper function to calculate style
                // Extract area number from database area name (e.g., "Area 13, South..." -> "13")
                function extractAreaNumber(areaName) {
                    if (!areaName) return null;
                    const match = areaName.match(/^Area\s+([\d-]+),/);
                    return match ? match[1] : null;
                }

                // Helper function to calculate style
                function getStyleForFeature(feature, isSelected = false) {
                    const props = feature.properties;
                    const gisAreaNumber = props.maNumber;

                    // Find matching catch data by area number
                    let areaData = { total: 0, surveys: 0 };
                    let matchedDbName = null;

                    for (const [dbName, dbData] of Object.entries(dataMap)) {
                        const dbAreaNumber = extractAreaNumber(dbName);
                        if (dbAreaNumber === gisAreaNumber) {
                            areaData = dbData;
                            matchedDbName = dbName;
                            break;
                        }
                    }

                    const intensity = Math.min(areaData.total / maxCatch, 1);
                    const fillOpacity = 0.3 + intensity * 0.5;

                    if (isSelected) {
                        return {
                            color: '#f59e0b',      // Amber-500 for selected border
                            weight: 4,
                            opacity: 1,
                            fillColor: '#fbbf24',  // Amber-400 for selected fill
                            fillOpacity: 0.7
                        };
                    }

                    return {
                        color: '#3182ce',
                        weight: 2,
                        opacity: 0.8,
                        fillColor: '#60a5fa',
                        fillOpacity: fillOpacity
                    };
                }
            
                // If layer already exists, just update styling
                if (marineAreasLayer) {
                    console.log('Updating existing marine areas layer styling');

                    // Get selected areas from filter dropdown
                    const catchAreaSelect = document.getElementById('catchArea');
                    const selectedAreas = Array.from(catchAreaSelect.selectedOptions).map(opt => opt.value);

                    // Clear and rebuild selection tracking
                    selectedAreaLayers.clear();


                    marineAreasLayer.eachFeature(function(layer) {
                        const props = layer.feature.properties;
                        const gisAreaNumber = props.maNumber;

                        // Find matching database area by number
                        let dbAreaName = null;
                        let areaData = { total: 0, surveys: 0 };

                        for (const [dbName, dbData] of Object.entries(dataMap)) {
                            const dbAreaNumber = extractAreaNumber(dbName);
                            if (dbAreaNumber === gisAreaNumber) {
                                dbAreaName = dbName;
                                areaData = dbData;
                                break;
                            }
                        }

                        // Check if this area is selected in the filter
                        const isSelected = dbAreaName && selectedAreas.includes(dbAreaName);

                        // Apply appropriate styling
                        const style = getStyleForFeature(layer.feature, isSelected);
                        layer.setStyle(style);

                        // Track all selected areas
                        if (isSelected) {
                            selectedAreaLayers.add(layer);
                        }

                        // Update popup content
                        const displayName = dbAreaName || `${props.maName} (Area ${props.maNumber})`;

                        const wacSection = props.WAC ? 
                            `<p style="margin: 8px 0 4px 0; font-size: 0.85em; color: #718096;"><strong>WAC:</strong> ${props.WAC}</p>` : '';

                        const popupContent = `
                            <div style="font-family: sans-serif;">
                                <h3 style="margin: 0 0 8px 0; color: #2d3748; font-size: 1.1em;">
                                    ${displayName}
                                </h3>
                                <div style="border-top: 1px solid #e2e8f0; padding-top: 8px;">
                                    <p style="margin: 4px 0;"><strong>Total Catch:</strong> ${Math.round(areaData.total).toLocaleString()}</p>
                                    <p style="margin: 4px 0;"><strong>Surveys:</strong> ${areaData.surveys.toLocaleString()}</p>
                                </div>
                                ${wacSection}
                            </div>
                        `;
                        layer.setPopupContent(popupContent);
                    });

                    // Force map resize
                    setTimeout(() => {
                        if (map) {
                            map.invalidateSize();
                        }
                    }, 100);

                    return; // Exit - no need to recreate layer
                }

                // Create layer for the first time
                console.log('Creating new marine areas layer');
                mapLayers = [];

                const WDFW_MAPSERVER_URL = "https://geodataservices.wdfw.wa.gov/arcgis/rest/services/ApplicationServices/Marine_Areas/MapServer";
                const LAYER_INDEX = 3;

                marineAreasLayer = L.esri.featureLayer({
                    url: WDFW_MAPSERVER_URL + '/' + LAYER_INDEX,
                    style: getStyleForFeature,

                    onEachFeature: function(feature, layer) {
                        const props = feature.properties;

                        const gisAreaNumber = props.maNumber;

                        // Find matching database area by number
                        let dbAreaName = null;
                        let areaData = { total: 0, surveys: 0 };

                        for (const [dbName, dbData] of Object.entries(dataMap)) {
                            const dbAreaNumber = extractAreaNumber(dbName);
                            if (dbAreaNumber === gisAreaNumber) {
                                dbAreaName = dbName;
                                areaData = dbData;
                                break;
                            }
                        }

                        mapLayers.push(layer);

                        // Mouse hover effects
                        layer.on('mouseover', function(e) {
                            layer.setStyle({
                                weight: 4,
                                fillColor: '#facc15',
                                fillOpacity: 0.6
                            });
                            layer.bringToFront();
                        });

                        layer.on('mouseout', function(e) {
                            // Don't reset style if this is the selected area
                            const isSelected = selectedAreaLayers.has(layer);
                            const style = getStyleForFeature(feature, isSelected);
                            layer.setStyle(style);
                        });

                        // Click to toggle area selection
                        layer.on('click', function(e) {
                            if (dbAreaName) {
                                const catchAreaSelect = document.getElementById('catchArea');
                                
                                // Find the option for this area
                                let optionFound = false;
                                let isCurrentlySelected = false;
                                
                                for (let i = 0; i < catchAreaSelect.options.length; i++) {
                                    if (catchAreaSelect.options[i].value === dbAreaName) {
                                        optionFound = true;
                                        isCurrentlySelected = catchAreaSelect.options[i].selected;
                                        // Toggle the selection
                                        catchAreaSelect.options[i].selected = !isCurrentlySelected;
                                        break;
                                    }
                                }
                                
                                if (optionFound) {
                                    // Update visual styling immediately
                                    if (!isCurrentlySelected) {
                                        // Was not selected, now is - add to selection set
                                        selectedAreaLayers.add(layer);
                                        const selectedStyle = getStyleForFeature(feature, true);
                                        layer.setStyle(selectedStyle);
                                        layer.bringToFront();
                                    } else {
                                        // Was selected, now is not - remove from selection set
                                        selectedAreaLayers.delete(layer);
                                        const unselectedStyle = getStyleForFeature(feature, false);
                                        layer.setStyle(unselectedStyle);
                                    }
                                    
                                    // Apply filters to update charts
                                    applyFilters();
                                }
                            }
                        });

                        // Popup content
                        const displayName = dbAreaName || `${props.maName} (Area ${props.maNumber})`;

                        const wacSection = props.WAC ? 
                            `<p style="margin: 8px 0 4px 0; font-size: 0.85em; color: #718096;"><strong>WAC:</strong> ${props.WAC}</p>` : '';

                        const popupContent = `
                            <div style="font-family: sans-serif;">
                                <h3 style="margin: 0 0 8px 0; color: #2d3748; font-size: 1.1em;">
                                    ${displayName}
                                </h3>
                                <div style="border-top: 1px solid #e2e8f0; padding-top: 8px;">
                                    <p style="margin: 4px 0;"><strong>Total Catch:</strong> ${Math.round(areaData.total).toLocaleString()}</p>
                                    <p style="margin: 4px 0;"><strong>Surveys:</strong> ${areaData.surveys.toLocaleString()}</p>
                                </div>
                                ${wacSection}
                            </div>
                        `;
                        layer.bindPopup(popupContent);
                    }
                }).addTo(map);

                // Handle loading events
                marineAreasLayer.on('load', function(e) {
                    console.log('Marine areas loaded successfully');

                    // Only fit bounds on initial load to prevent zoom reset
                    if (!initialMapLoadComplete && mapLayers.length > 0) {
                        const group = L.featureGroup(mapLayers);
                        const bounds = group.getBounds();
                        if (bounds.isValid()) {
                            map.fitBounds(bounds, { padding: [20, 20] });
                            initialMapLoadComplete = true;
                        }
                    }
                });

                marineAreasLayer.on('error', function(e) {
                    console.error('Error loading marine areas:', e);
                    document.getElementById('map').innerHTML = 
                        '<div style="padding: 20px; text-align: center; color: #e53e3e;">Error loading WDFW marine area data. Check console for details.</div>';
                });

                // Force map resize
                setTimeout(() => {
                    if (map) {
                        map.invalidateSize();
                    }
                }, 300);

            } catch (error) {
                console.error('Error creating map:', error);
                document.getElementById('map').innerHTML = 
                    '<div style="padding: 20px; text-align: center; color: #e53e3e;">Error loading map: ' + error.message + '</div>';
            }
        }
        function createTrendChart(data) {
            const ctx = document.getElementById('trendChart').getContext('2d');

            // Destroy existing chart if it exists
            if (charts.trend) {
                charts.trend.destroy();
            }

            // Define colors for each species
            const speciesColors = {
                'chinook': { border: '#e53e3e', bg: 'rgba(229, 62, 62, 0.1)' },
                'coho': { border: '#3182ce', bg: 'rgba(49, 130, 206, 0.1)' },
                'chum': { border: '#805ad5', bg: 'rgba(128, 90, 213, 0.1)' },
                'pink': { border: '#ed64a6', bg: 'rgba(237, 100, 166, 0.1)' },
                'sockeye': { border: '#38a169', bg: 'rgba(56, 161, 105, 0.1)' },
                'lingcod': { border: '#d69e2e', bg: 'rgba(214, 158, 46, 0.1)' },
                'halibut': { border: '#dd6b20', bg: 'rgba(221, 107, 32, 0.1)' }
            };

            // Build datasets based on what species are in the data
            const datasets = [];
            if (data.length > 0) {
                const sampleData = data[0];
                const availableSpecies = Object.keys(sampleData).filter(key => key !== 'period');

                availableSpecies.forEach(species => {
                    const color = speciesColors[species] || { border: '#667eea', bg: 'rgba(102, 126, 234, 0.1)' };
                    datasets.push({
                        label: species.charAt(0).toUpperCase() + species.slice(1),
                        data: data.map(d => Math.round(d[species] || 0)),
                        borderColor: color.border,
                        backgroundColor: color.bg,
                        tension: 0.4
                    });
                });
            }

            charts.trend = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: data.map(d => d.period),
                    datasets: datasets
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: true,
                    plugins: { legend: { position: 'top' } },
                    scales: { 
                        y: { beginAtZero: true },
                        x: {
                            ticks: {
                                maxRotation: 45,
                                minRotation: 45,
                                autoSkip: true,
                                maxTicksLimit: 20
                            }
                        }
                    }
                }
            });
        }

        function createSpeciesChart(data) {
            const ctx = document.getElementById('speciesChart').getContext('2d');

            // Destroy existing chart if it exists
            if (charts.species) {
                charts.species.destroy();
            }

            charts.species = new Chart(ctx, {
                type: 'doughnut',
                data: {
                    labels: ['Chinook', 'Coho', 'Chum', 'Pink', 'Sockeye', 'Lingcod', 'Halibut'],
                    datasets: [{
                        data: [
                            Math.round(data.chinook),
                            Math.round(data.coho),
                            Math.round(data.chum),
                            Math.round(data.pink),
                            Math.round(data.sockeye),
                            Math.round(data.lingcod),
                            Math.round(data.halibut)
                        ],
                        backgroundColor: ['#e53e3e', '#3182ce', '#805ad5', '#ed64a6', '#38a169', '#d69e2e', '#dd6b20']
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: true,
                    plugins: { legend: { position: 'right' } }
                }
            });
        }

        function createAreaChart(data) {
            const ctx = document.getElementById('areaChart').getContext('2d');

            // Destroy existing chart if it exists
            if (charts.area) {
                charts.area.destroy();
            }

            charts.area = new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: data.map(d => d.area.length > 30 ? d.area.substring(0, 30) + '...' : d.area),
                    datasets: [{
                        label: 'Total Salmon Catch',
                        data: data.map(d => Math.round(d.total)),
                        backgroundColor: '#667eea'
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: true,
                    indexAxis: 'y',
                    plugins: { legend: { display: false } },
                    scales: { x: { beginAtZero: true } }
                }
            });
        }

        function createMonthlyChart(data) {
            const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
            const ctx = document.getElementById('monthlyChart').getContext('2d');

            // Destroy existing chart if it exists
            if (charts.monthly) {
                charts.monthly.destroy();
            }

            charts.monthly = new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: months,
                    datasets: [{
                        label: 'Total Salmon Catch',
                        data: data.map(d => Math.round(d.total)),
                        backgroundColor: '#764ba2'
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: true,
                    plugins: { legend: { display: false } },
                    scales: { y: { beginAtZero: true } }
                }
            });
        }

        // Load data on page load
        // Check for data updates automatically
        async function checkForUpdates() {
            try {
                console.log('Checking for data updates...');
                const response = await fetch('/api/update');
                const data = await response.json();
                
                if (data.updated) {
                    console.log('✅ Data updated:', data.message);
                    // Reload data after successful update
                    setTimeout(() => {
                        loadData();
                    }, 1000);
                } else if (data.success) {
                    console.log('✓ Data current:', data.message);
                } else {
                    console.log('Update check:', data.message);
                }
            } catch (err) {
                console.error('Error checking for updates:', err);
            }
        }


        async function init() {
            // Start update check (don't wait for it)
            checkForUpdates();
            
            await loadFilterOptions();
            await loadData();
        }

        init();
    </script>
</body>
</html>"""
        self.send_response(200)
        self.send_header('Content-Type', 'text/html')
        self.end_headers()
        self.wfile.write(html.encode())

    def serve_stats(self, params):
        """Overall statistics"""
        conn = self.get_db_connection()
        cursor = conn.cursor()

        where_clause, query_params = self.build_where_clause(params)

        query = f"""
            SELECT 
                COUNT(*) as total_records,
                SUM(anglers) as total_anglers,
                SUM(chinook) as total_chinook,
                SUM(coho) as total_coho,
                MIN(substr(sample_date, -4)) as min_year,
                MAX(substr(sample_date, -4)) as max_year
            FROM creel_records
            {where_clause}
        """

        cursor.execute(query, query_params)
        row = cursor.fetchone()
        conn.close()

        self.send_json({
            'total_records': row[0] or 0,
            'total_anglers': row[1] or 0,
            'total_chinook': row[2] or 0,
            'total_coho': row[3] or 0,
            'min_year': row[4] or 'N/A',
            'max_year': row[5] or 'N/A'
        })

    def serve_yearly_data(self, params):
        """Yearly catch trends"""
        conn = self.get_db_connection()
        cursor = conn.cursor()

        where_clause, query_params = self.build_where_clause(params)

        query = f"""
            SELECT 
                substr(sample_date, -4) as year,
                SUM(chinook) as chinook,
                SUM(coho) as coho,
                SUM(chum) as chum,
                SUM(pink) as pink,
                SUM(sockeye) as sockeye
            FROM creel_records
            {where_clause}
            {"AND" if where_clause else "WHERE"} length(sample_date) > 0
            GROUP BY year
            ORDER BY year
        """

        cursor.execute(query, query_params)
        rows = cursor.fetchall()
        conn.close()

        data = [{
            'year': row[0],
            'chinook': row[1] or 0,
            'coho': row[2] or 0,
            'chum': row[3] or 0,
            'pink': row[4] or 0,
            'sockeye': row[5] or 0
        } for row in rows]

        self.send_json(data)

    def serve_trend_data(self, params):
        """Trend data with configurable time granularity"""
        conn = self.get_db_connection()
        cursor = conn.cursor()

        time_unit = params.get('time_unit', ['yearly'])[0]
        where_clause, query_params = self.build_where_clause(params)

        # Get list of species to display
        species_list = self.get_species_list(params)

        # Build species SELECT columns
        species_select = ', '.join([f"SUM({s}) as {s}" for s in species_list])

        if time_unit == 'daily':
            query = f"""
                SELECT 
                    sample_date as period,
                    {species_select}
                FROM creel_records
                {where_clause}
                {"AND" if where_clause else "WHERE"} length(sample_date) > 0
                GROUP BY sample_date
                ORDER BY substr(sample_date, -4), 
                         CASE substr(sample_date, 1, 3)
                             WHEN 'Jan' THEN 1 WHEN 'Feb' THEN 2 WHEN 'Mar' THEN 3
                             WHEN 'Apr' THEN 4 WHEN 'May' THEN 5 WHEN 'Jun' THEN 6
                             WHEN 'Jul' THEN 7 WHEN 'Aug' THEN 8 WHEN 'Sep' THEN 9
                             WHEN 'Oct' THEN 10 WHEN 'Nov' THEN 11 WHEN 'Dec' THEN 12
                         END,
                         CAST(substr(sample_date, instr(sample_date, ' ') + 1, 
                              instr(sample_date, ',') - instr(sample_date, ' ') - 1) AS INTEGER)
            """
        elif time_unit == 'weekly':
            # Group by year-month-week (week of month)
            query = f"""
                SELECT 
                    substr(sample_date, -4) || '-' ||
                    substr(sample_date, 1, 3) || '-W' || 
                    CAST((CAST(substr(sample_date, instr(sample_date, ' ') + 1, 
                        instr(sample_date, ',') - instr(sample_date, ' ') - 1) AS INTEGER) - 1) / 7 + 1 AS INTEGER) as period,
                    {species_select}
                FROM creel_records
                {where_clause}
                {"AND" if where_clause else "WHERE"} length(sample_date) > 0
                GROUP BY period
                ORDER BY substr(period, 1, 4),
                         CASE substr(period, 6, 3)
                             WHEN 'Jan' THEN 1 WHEN 'Feb' THEN 2 WHEN 'Mar' THEN 3
                             WHEN 'Apr' THEN 4 WHEN 'May' THEN 5 WHEN 'Jun' THEN 6
                             WHEN 'Jul' THEN 7 WHEN 'Aug' THEN 8 WHEN 'Sep' THEN 9
                             WHEN 'Oct' THEN 10 WHEN 'Nov' THEN 11 WHEN 'Dec' THEN 12
                         END,
                         CAST(substr(period, instr(period, '-W') + 2) AS INTEGER)
            """
        elif time_unit == 'monthly':
            query = f"""
                SELECT 
                    substr(sample_date, -4) || '-' || 
                    substr('0' || CASE substr(sample_date, 1, 3)
                        WHEN 'Jan' THEN '01' WHEN 'Feb' THEN '02' WHEN 'Mar' THEN '03'
                        WHEN 'Apr' THEN '04' WHEN 'May' THEN '05' WHEN 'Jun' THEN '06'
                        WHEN 'Jul' THEN '07' WHEN 'Aug' THEN '08' WHEN 'Sep' THEN '09'
                        WHEN 'Oct' THEN '10' WHEN 'Nov' THEN '11' WHEN 'Dec' THEN '12'
                    END, -2) as period,
                    {species_select}
                FROM creel_records
                {where_clause}
                {"AND" if where_clause else "WHERE"} length(sample_date) > 0
                GROUP BY period
                ORDER BY period
            """
        else:  # yearly (default)
            query = f"""
                SELECT 
                    substr(sample_date, -4) as period,
                    {species_select}
                FROM creel_records
                {where_clause}
                {"AND" if where_clause else "WHERE"} length(sample_date) > 0
                GROUP BY period
                ORDER BY period
            """

        cursor.execute(query, query_params)
        rows = cursor.fetchall()
        conn.close()

        # Build response with dynamic species
        data = []
        for row in rows:
            item = {'period': row[0]}
            for i, species in enumerate(species_list):
                item[species] = row[i + 1] or 0
            data.append(item)

        self.send_json(data)

    def serve_species_totals(self, params):
        """Total catch by species"""
        conn = self.get_db_connection()
        cursor = conn.cursor()

        where_clause, query_params = self.build_where_clause(params)

        query = f"""
            SELECT 
                SUM(chinook) as chinook,
                SUM(coho) as coho,
                SUM(chum) as chum,
                SUM(pink) as pink,
                SUM(sockeye) as sockeye,
                SUM(lingcod) as lingcod,
                SUM(halibut) as halibut
            FROM creel_records
            {where_clause}
        """

        cursor.execute(query, query_params)
        row = cursor.fetchone()
        conn.close()

        self.send_json({
            'chinook': row[0] or 0,
            'coho': row[1] or 0,
            'chum': row[2] or 0,
            'pink': row[3] or 0,
            'sockeye': row[4] or 0,
            'lingcod': row[5] or 0,
            'halibut': row[6] or 0
        })

    def serve_top_areas(self, params):
        """Top 10 catch areas"""
        conn = self.get_db_connection()
        cursor = conn.cursor()

        where_clause, query_params = self.build_where_clause(params)
        species_columns = self.get_species_columns(params)

        query = f"""
            SELECT 
                catch_area,
                SUM({species_columns}) as total_catch
            FROM creel_records
            {where_clause}
            {"AND" if where_clause else "WHERE"} catch_area != ''
            GROUP BY catch_area
            ORDER BY total_catch DESC
            LIMIT 10
        """

        cursor.execute(query, query_params)
        rows = cursor.fetchall()
        conn.close()

        data = [{'area': row[0], 'total': row[1] or 0} for row in rows]
        self.send_json(data)

    def serve_monthly_data(self, params):
        """Monthly catch distribution"""
        conn = self.get_db_connection()
        cursor = conn.cursor()

        where_clause, query_params = self.build_where_clause(params)
        species_columns = self.get_species_columns(params)

        query = f"""
            SELECT 
                CASE substr(sample_date, 1, 3)
                    WHEN 'Jan' THEN 1
                    WHEN 'Feb' THEN 2
                    WHEN 'Mar' THEN 3
                    WHEN 'Apr' THEN 4
                    WHEN 'May' THEN 5
                    WHEN 'Jun' THEN 6
                    WHEN 'Jul' THEN 7
                    WHEN 'Aug' THEN 8
                    WHEN 'Sep' THEN 9
                    WHEN 'Oct' THEN 10
                    WHEN 'Nov' THEN 11
                    WHEN 'Dec' THEN 12
                END as month,
                SUM({species_columns}) as total_catch
            FROM creel_records
            {where_clause}
            {"AND" if where_clause else "WHERE"} month IS NOT NULL
            GROUP BY month
            ORDER BY month
        """

        cursor.execute(query, query_params)
        rows = cursor.fetchall()
        conn.close()

        # Fill all 12 months
        monthly_totals = [0] * 12
        for row in rows:
            month = row[0]
            if month and 1 <= month <= 12:
                monthly_totals[month - 1] = row[1] or 0

        data = [{'month': i + 1, 'total': monthly_totals[i]} for i in range(12)]
        self.send_json(data)

    def serve_filter_options(self):
        """Get available filter options (years and catch areas)"""
        conn = self.get_db_connection()
        cursor = conn.cursor()

        # Get available years
        cursor.execute("""
            SELECT DISTINCT substr(sample_date, -4) as year
            FROM creel_records
            WHERE length(sample_date) > 0
            ORDER BY year
        """)
        years = [row[0] for row in cursor.fetchall() if row[0]]

        # Get catch areas
        cursor.execute("""
            SELECT DISTINCT catch_area
            FROM creel_records
            WHERE catch_area != ''
            ORDER BY catch_area
        """)
        areas = [row[0] for row in cursor.fetchall()]

        conn.close()

        self.send_json({
            'years': years,
            'areas': areas
        })

    def serve_map_data(self, params):
        """Get catch totals by area for map visualization"""
        conn = self.get_db_connection()
        cursor = conn.cursor()

        where_clause, query_params = self.build_where_clause(params)
        species_columns = self.get_species_columns(params)

        query = f"""
            SELECT 
                catch_area,
                SUM({species_columns}) as total_catch,
                COUNT(*) as survey_count
            FROM creel_records
            {where_clause}
            {"AND" if where_clause else "WHERE"} catch_area != ''
            GROUP BY catch_area
            ORDER BY total_catch DESC
        """

        cursor.execute(query, query_params)
        rows = cursor.fetchall()
        conn.close()

        data = [{'area': row[0], 'total': row[1] or 0, 'surveys': row[2] or 0} for row in rows]
        self.send_json(data)


    def _ensure_metadata_table(self, conn):
        """Ensure metadata table exists for storing last update time"""
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        conn.commit()

    def get_last_update_time(self):
        """Get the timestamp of the last data update from database"""
        try:
            conn = self.get_db_connection()
            self._ensure_metadata_table(conn)
            cursor = conn.cursor()
            
            cursor.execute("SELECT value FROM metadata WHERE key = 'last_update'")
            row = cursor.fetchone()
            conn.close()
            
            if row:
                return datetime.fromisoformat(row[0])
            return None
        except Exception as e:
            print(f"Error getting last update time: {e}")
            return None

    def set_last_update_time(self):
        """Record the current time as the last update time in database"""
        try:
            conn = self.get_db_connection()
            self._ensure_metadata_table(conn)
            cursor = conn.cursor()
            
            now = datetime.now().isoformat()
            cursor.execute("""
                INSERT OR REPLACE INTO metadata (key, value, updated_at)
                VALUES ('last_update', ?, ?)
            """, (now, now))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Warning: Could not write update timestamp: {e}")

    def serve_update_data(self):
        """Update data from WDFW if it's been more than 24 hours"""
        
        # Check if collector is available
        if WDFWCreelCollector is None:
            self.send_json({
                'success': False,
                'message': 'Data collector not available. Ensure main.py is in the same directory.',
                'last_update': None,
                'should_reload': False
            })
            return

        # Check last update time
        last_update = self.get_last_update_time()
        now = datetime.now()
        
        if last_update:
            time_since_update = now - last_update
            hours_since_update = time_since_update.total_seconds() / 3600
            
            # If updated within last 24 hours, don't update again
            if hours_since_update < 24:
                self.send_json({
                    'success': True,
                    'message': f'Data is current (updated {hours_since_update:.1f} hours ago)',
                    'last_update': last_update.isoformat(),
                    'next_update_available': (last_update + timedelta(days=1)).isoformat(),
                    'should_reload': False
                })
                return
        
        # Perform the update
        try:
            print("=" * 70)
            print("Starting automatic data update from WDFW...")
            print("=" * 70)
            
            collector = WDFWCreelCollector()
            
            try:
                # Fetch data (use max_years=13 as in main.py)
                collector.fetch_all_data(max_years=13)
                
                # Record update time
                self.set_last_update_time()
                
                # Get record count
                cursor = collector.conn.cursor()
                cursor.execute('SELECT COUNT(*) FROM creel_records')
                total_records = cursor.fetchone()[0]
                
                print("=" * 70)
                print(f"✅ Update completed successfully! Total records: {total_records:,}")
                print("=" * 70)
                
                # Upload database to GCS for persistence
                bucket_name = os.environ.get("GCS_BUCKET_NAME")
                if bucket_name:
                    upload_database_to_gcs(bucket_name, self.DB_PATH)
                else:
                    print("⚠️  GCS_BUCKET_NAME not set, database will not persist across deployments")
                
                self.send_json({
                    'success': True,
                    'message': f'Data updated successfully. Total records: {total_records:,}',
                    'last_update': datetime.now().isoformat(),
                    'records': total_records,
                    'should_reload': True
                })
                
            finally:
                collector.close()
                
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            print(f"❌ Error updating data: {error_details}")
            
            self.send_json({
                'success': False,
                'message': f'Error updating data: {str(e)}',
                'last_update': last_update.isoformat() if last_update else None,
                'should_reload': False
            })


def main():
    PORT = int(os.environ.get("PORT", 8080))

    # Database path (will be created on first request via auto-update)
    db_path = os.path.join("wdfw_creel_data", "creel_data.db")
    
    # Try to download existing database from GCS
    bucket_name = os.environ.get("GCS_BUCKET_NAME")
    if bucket_name:
        print(f"🪣 GCS Bucket: {bucket_name}")
        if not os.path.exists(db_path):
            download_database_from_gcs(bucket_name, db_path)
    else:
        print("⚠️  GCS_BUCKET_NAME not set, database will not persist across deployments")
    
    server = HTTPServer(('0.0.0.0', PORT), CreelDataHandler)

    print("=" * 70)
    print("🎣 WDFW CREEL DASHBOARD SERVER")
    print("=" * 70)
    
    if os.path.exists(db_path):
        print(f"✅ Database found: {os.path.abspath(db_path)}")
    else:
        print(f"⏳ Database will be created on first request")
        print(f"   Location: {os.path.abspath(db_path)}")
    
    print(f"\n🌐 Server running on port {PORT}")
    print(f"   Local: http://localhost:{PORT}")
    print(f"   Cloud Run: Listening on 0.0.0.0:{PORT}")
    print("\nPress Ctrl+C to stop the server")
    print("=" * 70)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n\n🛑 Server stopped")


if __name__ == "__main__":
    main()
