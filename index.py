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
                    const match = areaName.match(/^Area\\s+([\\d-]+),/);
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


                    // Also update custom polygon layers
                    if (window.customAreaLayers) {
                        Object.entries(window.customAreaLayers).forEach(([areaName, layerGroup]) => {
                            const isSelected = selectedAreas.includes(areaName);

                            layerGroup.eachLayer(function(layer) {
                                let areaData = { total: 0, surveys: 0 };
                                if (dataMap[areaName]) {
                                    areaData = dataMap[areaName];
                                }

                                const intensity = Math.min(areaData.total / maxCatch, 1);
                                const fillOpacity = 0.3 + intensity * 0.5;

                                if (isSelected) {
                                    selectedAreaLayers.add(layer);
                                    layer.setStyle({
                                        color: '#f59e0b',
                                        weight: 4,
                                        fillColor: '#fbbf24',
                                        fillOpacity: 0.7
                                    });
                                } else {
                                    selectedAreaLayers.delete(layer);
                                    layer.setStyle({
                                        color: '#3182ce',
                                        weight: 2,
                                        fillColor: '#3182ce',
                                        fillOpacity: fillOpacity
                                    });
                                }
                            });

                            // Keep custom layers on top
                            layerGroup.bringToFront();
                        });
                    }
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

                // Add custom area polygons for areas not in WDFW GIS layer
                const customAreaPolygons = {
                    "Bellingham Bay": {
                        "type": "Feature",
                        "properties": {
                            "name": "Bellingham Bay",
                            "description": "Waters of Bellingham and Padilla bays"
                        },
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [[
                                [-122.66991, 48.73174],
                                [-122.64793, 48.71588],
                                [-122.62012, 48.74849],
                                [-122.61017, 48.75574],
                                [-122.59867, 48.7692],
                                [-122.59094, 48.7787],
                                [-122.55901, 48.77723],
                                [-122.53429, 48.77463],
                                [-122.53017, 48.7683],
                                [-122.51713, 48.76366],
                                [-122.48571, 48.75155],
                                [-122.49155, 48.74261],
                                [-122.49687, 48.73717],
                                [-122.50631, 48.72789],
                                [-122.50769, 48.72359],
                                [-122.51747, 48.71826],
                                [-122.52022, 48.71577],
                                [-122.52022, 48.71203],
                                [-122.51541, 48.70444],
                                [-122.51558, 48.69946],
                                [-122.51455, 48.69867],
                                [-122.49799, 48.69583],
                                [-122.49207, 48.68507],
                                [-122.49086, 48.67651],
                                [-122.49052, 48.67118],
                                [-122.49292, 48.67016],
                                [-122.49447, 48.66954],
                                [-122.49378, 48.66807],
                                [-122.49481, 48.66716],
                                [-122.49773, 48.66767],
                                [-122.50031, 48.66795],
                                [-122.50056, 48.66676],
                                [-122.49816, 48.66591],
                                [-122.49859, 48.66472],
                                [-122.50082, 48.66404],
                                [-122.50108, 48.66302],
                                [-122.50194, 48.66489],
                                [-122.50305, 48.66585],
                                [-122.50872, 48.6696],
                                [-122.51181, 48.66914],
                                [-122.51224, 48.66773],
                                [-122.50975, 48.66438],
                                [-122.50408, 48.65639],
                                [-122.49378, 48.65219],
                                [-122.49361, 48.65009],
                                [-122.4852, 48.6413],
                                [-122.46469, 48.62604],
                                [-122.44623, 48.61929],
                                [-122.44623, 48.61589],
                                [-122.44434, 48.61385],
                                [-122.44074, 48.61316],
                                [-122.43834, 48.61078],
                                [-122.43628, 48.6084],
                                [-122.43387, 48.60635],
                                [-122.42632, 48.6],
                                [-122.43044, 48.59285],
                                [-122.44349, 48.57547],
                                [-122.45378, 48.56752],
                                [-122.4579, 48.56604],
                                [-122.46117, 48.56673],
                                [-122.45979, 48.56309],
                                [-122.45979, 48.56116],
                                [-122.46357, 48.56093],
                                [-122.46632, 48.55945],
                                [-122.46426, 48.55684],
                                [-122.46146, 48.55703],
                                [-122.45707, 48.55508],
                                [-122.45851, 48.5548],
                                [-122.4602, 48.55551],
                                [-122.46139, 48.55548],
                                [-122.46278, 48.55534],
                                [-122.46421, 48.55553],
                                [-122.46546, 48.55549],
                                [-122.46632, 48.55536],
                                [-122.4678, 48.5562],
                                [-122.47069, 48.5573],
                                [-122.4755, 48.55536],
                                [-122.48116, 48.55985],
                                [-122.48477, 48.55974],
                                [-122.48752, 48.55906],
                                [-122.48606, 48.55764],
                                [-122.48563, 48.55553],
                                [-122.48812, 48.5569],
                                [-122.49224, 48.56014],
                                [-122.49438, 48.56337],
                                [-122.49704, 48.5665],
                                [-122.49387, 48.56763],
                                [-122.48829, 48.56866],
                                [-122.48692, 48.56991],
                                [-122.49018, 48.57081],
                                [-122.49301, 48.57127],
                                [-122.49627, 48.57309],
                                [-122.4961, 48.57519],
                                [-122.49473, 48.57627],
                                [-122.53927, 48.57672],
                                [-122.5421, 48.57956],
                                [-122.55052, 48.58212],
                                [-122.55043, 48.58637],
                                [-122.55343, 48.58899],
                                [-122.55635, 48.5891],
                                [-122.55747, 48.58717],
                                [-122.55738, 48.58558],
                                [-122.56039, 48.58399],
                                [-122.5615, 48.58194],
                                [-122.55996, 48.58047],
                                [-122.55755, 48.57945],
                                [-122.55704, 48.57769],
                                [-122.55755, 48.57581],
                                [-122.55816, 48.57451],
                                [-122.55386, 48.57485],
                                [-122.53472, 48.57388],
                                [-122.52271, 48.56707],
                                [-122.50588, 48.56457],
                                [-122.50271, 48.5611],
                                [-122.50125, 48.55832],
                                [-122.49928, 48.55559],
                                [-122.49953, 48.55252],
                                [-122.50073, 48.54957],
                                [-122.49928, 48.54758],
                                [-122.49893, 48.54536],
                                [-122.49833, 48.54321],
                                [-122.49619, 48.53991],
                                [-122.49241, 48.53786],
                                [-122.48932, 48.53633],
                                [-122.48692, 48.53525],
                                [-122.48769, 48.53309],
                                [-122.48408, 48.52138],
                                [-122.48374, 48.51768],
                                [-122.48674, 48.51478],
                                [-122.48786, 48.51302],
                                [-122.48674, 48.51058],
                                [-122.48297, 48.49096],
                                [-122.47825, 48.48111],
                                [-122.4719, 48.47793],
                                [-122.46915, 48.47383],
                                [-122.47078, 48.47025],
                                [-122.47438, 48.4682],
                                [-122.50331, 48.45898],
                                [-122.53678, 48.46638],
                                [-122.55936, 48.50137],
                                [-122.57584, 48.49591],
                                [-122.57652, 48.48339],
                                [-122.57309, 48.47019],
                                [-122.57549, 48.46427],
                                [-122.5827, 48.46632],
                                [-122.59644, 48.49226],
                                [-122.60124, 48.50751],
                                [-122.59506, 48.51797],
                                [-122.60124, 48.52274],
                                [-122.62047, 48.5207],
                                [-122.66922, 48.50591],
                                [-122.67746, 48.50751],
                                [-122.64725, 48.5282],
                                [-122.63042, 48.52706],
                                [-122.61944, 48.52979],
                                [-122.60845, 48.53252],
                                [-122.60536, 48.5357],
                                [-122.59712, 48.5357],
                                [-122.59232, 48.53616],
                                [-122.58614, 48.53275],
                                [-122.57618, 48.52911],
                                [-122.5724, 48.52888],
                                [-122.57206, 48.53434],
                                [-122.57343, 48.54366],
                                [-122.58064, 48.55093],
                                [-122.59575, 48.55684],
                                [-122.6033, 48.56002],
                                [-122.61532, 48.56548],
                                [-122.62218, 48.57047],
                                [-122.62939, 48.57479],
                                [-122.63214, 48.57911],
                                [-122.63695, 48.5841],
                                [-122.64175, 48.58864],
                                [-122.64484, 48.58887],
                                [-122.65695, 48.60956],
                                [-122.65703, 48.61214],
                                [-122.6615, 48.61368],
                                [-122.66201, 48.6202],
                                [-122.67076, 48.6248],
                                [-122.67351, 48.62979],
                                [-122.7575, 48.6934],
                                [-122.71179, 48.78696],
                                [-122.66991, 48.73174]
                            ]]
                        }
                    },
                    "Commencement Bay": {
                        "type": "Feature",
                        "properties": {
                            "name": "Commencement Bay",
                            "description": ""
                        },
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [[
                                [-122.41725, 47.29621],
                                [-122.46122, 47.27504],
                                [-122.45619, 47.27387],
                                [-122.4531, 47.27311],
                                [-122.45011, 47.2716],
                                [-122.44719, 47.26927],
                                [-122.4453, 47.26776],
                                [-122.44084, 47.26391],
                                [-122.43912, 47.26182],
                                [-122.40686, 47.28546],
                                [-122.41167, 47.29122],
                                [-122.41725, 47.29621]
                            ]]
                        }
                    },
                    "Dungeness Bay": {
                        "type": "Feature",
                        "properties": {
                            "name": "Dungeness Bay",
                            "description": ""
                        },
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [[
                                [-123.09864, 48.18354],
                                [-123.08792, 48.18961],
                                [-123.04645, 48.09723],
                                [-123.05898, 48.11434],
                                [-123.06859, 48.12161],
                                [-123.08129, 48.12554],
                                [-123.08768, 48.12886],
                                [-123.09982, 48.13697],
                                [-123.10973, 48.14582],
                                [-123.11436, 48.15025],
                                [-123.11758, 48.15214],
                                [-123.12153, 48.15292],
                                [-123.12196, 48.1522],
                                [-123.12466, 48.15272],
                                [-123.12903, 48.15429],
                                [-123.13011, 48.15398],
                                [-123.13058, 48.15246],
                                [-123.13238, 48.15086],
                                [-123.13491, 48.15063],
                                [-123.14173, 48.15114],
                                [-123.14439, 48.15189],
                                [-123.15036, 48.15398],
                                [-123.15048, 48.15498],
                                [-123.15113, 48.15567],
                                [-123.15164, 48.15446],
                                [-123.1522, 48.15275],
                                [-123.1528, 48.1512],
                                [-123.15383, 48.1504],
                                [-123.16159, 48.15011],
                                [-123.17202, 48.14773],
                                [-123.1779, 48.1463],
                                [-123.18201, 48.14676],
                                [-123.18472, 48.14653],
                                [-123.18407, 48.14796],
                                [-123.17828, 48.15346],
                                [-123.17476, 48.15604],
                                [-123.17206, 48.1583],
                                [-123.16876, 48.16042],
                                [-123.15203, 48.17195],
                                [-123.14761, 48.1741],
                                [-123.14525, 48.17499],
                                [-123.14272, 48.17544],
                                [-123.13491, 48.17513],
                                [-123.13658, 48.17367],
                                [-123.13791, 48.17192],
                                [-123.1389, 48.17046],
                                [-123.13984, 48.16921],
                                [-123.14032, 48.16823],
                                [-123.14113, 48.167],
                                [-123.14156, 48.16663],
                                [-123.14177, 48.16769],
                                [-123.14169, 48.16895],
                                [-123.1416, 48.17044],
                                [-123.14023, 48.17138],
                                [-123.13997, 48.17207],
                                [-123.14066, 48.17344],
                                [-123.14057, 48.17413],
                                [-123.14147, 48.17419],
                                [-123.14208, 48.17356],
                                [-123.14263, 48.17104],
                                [-123.14255, 48.16803],
                                [-123.14246, 48.16617],
                                [-123.1425, 48.16563],
                                [-123.14246, 48.16477],
                                [-123.14272, 48.16371],
                                [-123.14327, 48.16225],
                                [-123.1437, 48.1609],
                                [-123.14422, 48.15993],
                                [-123.14507, 48.15927],
                                [-123.14559, 48.15841],
                                [-123.14542, 48.15713],
                                [-123.14464, 48.15652],
                                [-123.14327, 48.15635],
                                [-123.14207, 48.15667],
                                [-123.14147, 48.15776],
                                [-123.14104, 48.1593],
                                [-123.13984, 48.16348],
                                [-123.13885, 48.16614],
                                [-123.13761, 48.16823],
                                [-123.13658, 48.16972],
                                [-123.13499, 48.17175],
                                [-123.13349, 48.1735],
                                [-123.13208, 48.17476],
                                [-123.13027, 48.17556],
                                [-123.12843, 48.17625],
                                [-123.1268, 48.1767],
                                [-123.12564, 48.17705],
                                [-123.12508, 48.17708],
                                [-123.12586, 48.17659],
                                [-123.12689, 48.17647],
                                [-123.12723, 48.17605],
                                [-123.12706, 48.17556],
                                [-123.12603, 48.17556],
                                [-123.12397, 48.17599],
                                [-123.1159, 48.18002],
                                [-123.11327, 48.18054],
                                [-123.11216, 48.18074],
                                [-123.10928, 48.18077],
                                [-123.10444, 48.1818],
                                [-123.10092, 48.18257],
                                [-123.09864, 48.18354]
                            ]]
                        }
                    },
                    "Hoodsport Hatchery": {
                        "type": "Feature",
                        "properties": {
                            "name": "Hoodsport Hatchery",
                            "description": ""
                        },
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [[
                                [-123.13859, 47.40718],
                                [-123.1389, 47.40646],
                                [-123.13821, 47.40634],
                                [-123.13811, 47.4064],
                                [-123.13802, 47.40648],
                                [-123.13796, 47.40655],
                                [-123.13791, 47.40664],
                                [-123.13787, 47.40674],
                                [-123.13786, 47.40681],
                                [-123.13785, 47.40688],
                                [-123.13783, 47.40695],
                                [-123.13783, 47.40701],
                                [-123.13859, 47.40718]
                            ]]
                        }
                    },
                    "Inner Elliot Bay Fishery Area": {
                        "type": "Feature",
                        "properties": {
                            "name": "Inner Elliot Bay Fishery Area",
                            "description": ""
                        },
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [[
                                [-122.43606, 47.66196],
                                [-122.42091, 47.57632],
                                [-122.41728, 47.57771],
                                [-122.40144, 47.58394],
                                [-122.3914, 47.5932],
                                [-122.38583, 47.59563],
                                [-122.38205, 47.59424],
                                [-122.38085, 47.59146],
                                [-122.38042, 47.59007],
                                [-122.37167, 47.58347],
                                [-122.36884, 47.58509],
                                [-122.36266, 47.58509],
                                [-122.34387, 47.59181],
                                [-122.34078, 47.59928],
                                [-122.34104, 47.60431],
                                [-122.37555, 47.62583],
                                [-122.3958, 47.62699],
                                [-122.40061, 47.6315],
                                [-122.41639, 47.64053],
                                [-122.41879, 47.64758],
                                [-122.42514, 47.65556],
                                [-122.43606, 47.66196]
                            ]]
                        }
                    },
                    "Quilcene, Dabob Bay": {
                        "type": "Feature",
                        "properties": {
                            "name": "Quilcene, Dabob Bay",
                            "description": ""
                        },
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [[
                                [-122.88488, 47.7227],
                                [-122.81351, 47.72454],
                                [-122.81317, 47.72755],
                                [-122.80939, 47.73009],
                                [-122.80751, 47.73297],
                                [-122.80871, 47.73713],
                                [-122.81128, 47.74244],
                                [-122.81111, 47.74625],
                                [-122.80922, 47.74914],
                                [-122.80528, 47.75294],
                                [-122.80202, 47.75664],
                                [-122.79996, 47.75941],
                                [-122.80047, 47.76356],
                                [-122.7967, 47.7661],
                                [-122.79635, 47.76991],
                                [-122.7967, 47.77406],
                                [-122.79481, 47.77717],
                                [-122.79292, 47.78167],
                                [-122.79086, 47.78467],
                                [-122.78949, 47.78825],
                                [-122.78949, 47.79205],
                                [-122.7888, 47.79551],
                                [-122.78915, 47.79817],
                                [-122.7876, 47.80139],
                                [-122.78692, 47.80416],
                                [-122.78949, 47.80635],
                                [-122.79224, 47.80797],
                                [-122.79515, 47.80993],
                                [-122.79773, 47.81281],
                                [-122.79567, 47.81627],
                                [-122.79532, 47.82042],
                                [-122.79807, 47.8248],
                                [-122.80202, 47.82768],
                                [-122.80613, 47.83183],
                                [-122.80528, 47.84151],
                                [-122.80785, 47.84681],
                                [-122.80459, 47.84969],
                                [-122.80665, 47.85418],
                                [-122.80991, 47.8574],
                                [-122.813, 47.8589],
                                [-122.81265, 47.85452],
                                [-122.81197, 47.85164],
                                [-122.81283, 47.84715],
                                [-122.81368, 47.84392],
                                [-122.81643, 47.84174],
                                [-122.81918, 47.83966],
                                [-122.82123, 47.83678],
                                [-122.82175, 47.83344],
                                [-122.82141, 47.82975],
                                [-122.82226, 47.8248],
                                [-122.82484, 47.82053],
                                [-122.82347, 47.81846],
                                [-122.819, 47.81223],
                                [-122.81557, 47.80785],
                                [-122.8178, 47.80047],
                                [-122.8202, 47.79425],
                                [-122.82192, 47.78963],
                                [-122.83084, 47.78294],
                                [-122.84354, 47.77798],
                                [-122.85281, 47.7796],
                                [-122.85555, 47.78237],
                                [-122.85384, 47.78548],
                                [-122.85041, 47.79309],
                                [-122.84955, 47.79701],
                                [-122.84732, 47.80024],
                                [-122.84817, 47.80843],
                                [-122.84972, 47.81177],
                                [-122.85195, 47.81627],
                                [-122.85281, 47.82341],
                                [-122.85487, 47.82583],
                                [-122.85899, 47.82572],
                                [-122.86276, 47.82341],
                                [-122.86602, 47.82203],
                                [-122.86654, 47.81419],
                                [-122.86859, 47.81189],
                                [-122.86825, 47.80843],
                                [-122.86636, 47.80589],
                                [-122.86774, 47.79943],
                                [-122.86791, 47.79701],
                                [-122.86619, 47.78583],
                                [-122.86465, 47.77798],
                                [-122.8619, 47.76968],
                                [-122.85778, 47.76506],
                                [-122.85092, 47.76264],
                                [-122.84886, 47.75375],
                                [-122.84955, 47.74994],
                                [-122.85195, 47.74706],
                                [-122.85178, 47.74486],
                                [-122.85178, 47.74175],
                                [-122.85144, 47.73817],
                                [-122.85367, 47.73574],
                                [-122.85923, 47.73586],
                                [-122.86232, 47.74117],
                                [-122.86472, 47.74371],
                                [-122.87125, 47.74371],
                                [-122.87399, 47.7384],
                                [-122.87227, 47.73494],
                                [-122.87227, 47.73147],
                                [-122.87777, 47.73032],
                                [-122.88051, 47.73147],
                                [-122.88326, 47.73032],
                                [-122.88488, 47.7227]
                            ]]
                        }
                    },
                    "Sinclair Inlet": {
                        "type": "Feature",
                        "properties": {
                            "name": "Sinclair Inlet",
                            "description": ""
                        },
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [[
                                [-122.5929, 47.66342],
                                [-122.6125, 47.6631],
                                [-122.61503, 47.65284],
                                [-122.61572, 47.65174],
                                [-122.61816, 47.65128],
                                [-122.61894, 47.65056],
                                [-122.62335, 47.65128],
                                [-122.62743, 47.65174],
                                [-122.62601, 47.65096],
                                [-122.62293, 47.65085],
                                [-122.62125, 47.65021],
                                [-122.62018, 47.6496],
                                [-122.61808, 47.65015],
                                [-122.61688, 47.65033],
                                [-122.60984, 47.64694],
                                [-122.60293, 47.64423],
                                [-122.60323, 47.64191],
                                [-122.6007, 47.63821],
                                [-122.59268, 47.63856],
                                [-122.59142, 47.6374],
                                [-122.59108, 47.63396],
                                [-122.59185, 47.62766],
                                [-122.59571, 47.61374],
                                [-122.59545, 47.61099],
                                [-122.59498, 47.60955],
                                [-122.59618, 47.60749],
                                [-122.59826, 47.60243],
                                [-122.59195, 47.59647],
                                [-122.5918, 47.59498],
                                [-122.59264, 47.59285],
                                [-122.5935, 47.59168],
                                [-122.59404, 47.5908],
                                [-122.59492, 47.59003],
                                [-122.59541, 47.58936],
                                [-122.59571, 47.58887],
                                [-122.5959, 47.5864],
                                [-122.59981, 47.57909],
                                [-122.60311, 47.57401],
                                [-122.60775, 47.5688],
                                [-122.61039, 47.56767],
                                [-122.61272, 47.56735],
                                [-122.61423, 47.56752],
                                [-122.61508, 47.56798],
                                [-122.6162, 47.56882],
                                [-122.61734, 47.56963],
                                [-122.618, 47.57032],
                                [-122.62283, 47.56913],
                                [-122.62259, 47.5679],
                                [-122.62313, 47.56526],
                                [-122.62317, 47.56439],
                                [-122.62386, 47.56267],
                                [-122.62454, 47.56241],
                                [-122.62514, 47.56215],
                                [-122.62495, 47.56128],
                                [-122.62549, 47.56096],
                                [-122.62784, 47.55695],
                                [-122.63505, 47.55516],
                                [-122.63848, 47.55261],
                                [-122.64345, 47.55127],
                                [-122.65632, 47.55058],
                                [-122.6619, 47.55017],
                                [-122.66533, 47.54878],
                                [-122.6716, 47.54681],
                                [-122.67297, 47.54444],
                                [-122.67434, 47.54224],
                                [-122.67507, 47.53818],
                                [-122.67953, 47.53598],
                                [-122.68314, 47.53407],
                                [-122.69703, 47.52816],
                                [-122.69377, 47.527],
                                [-122.69086, 47.52659],
                                [-122.68605, 47.52734],
                                [-122.67833, 47.52995],
                                [-122.66829, 47.53262],
                                [-122.66297, 47.53957],
                                [-122.64796, 47.53778],
                                [-122.63886, 47.54322],
                                [-122.63475, 47.54316],
                                [-122.62539, 47.54397],
                                [-122.6211, 47.54826],
                                [-122.6181, 47.54791],
                                [-122.60781, 47.54687],
                                [-122.59639, 47.56054],
                                [-122.59013, 47.56587],
                                [-122.58224, 47.57143],
                                [-122.58147, 47.57369],
                                [-122.57718, 47.5749],
                                [-122.57477, 47.57763],
                                [-122.57186, 47.5811],
                                [-122.56997, 47.58278],
                                [-122.56885, 47.58509],
                                [-122.56765, 47.59065],
                                [-122.57383, 47.5932],
                                [-122.57675, 47.59783],
                                [-122.57658, 47.6031],
                                [-122.57589, 47.60958],
                                [-122.57495, 47.61432],
                                [-122.57846, 47.62601],
                                [-122.57872, 47.63752],
                                [-122.57915, 47.64255],
                                [-122.57692, 47.64353],
                                [-122.5728, 47.64469],
                                [-122.5728, 47.64608],
                                [-122.57623, 47.64492],
                                [-122.57941, 47.64463],
                                [-122.58224, 47.64608],
                                [-122.58507, 47.65117],
                                [-122.5929, 47.66342]
                            ]]
                        }
                    },
                    "Tulalip Terminal Area": {
                        "type": "Feature",
                        "properties": {
                            "name": "Tulalip Terminal Area",
                            "description": ""
                        },
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [[
                                [-122.33276, 48.07601],
                                [-122.32186, 48.08129],
                                [-122.31118, 48.07607],
                                [-122.30106, 48.07186],
                                [-122.30033, 48.07008],
                                [-122.29956, 48.06899],
                                [-122.29844, 48.06799],
                                [-122.29822, 48.06649],
                                [-122.29831, 48.06598],
                                [-122.29762, 48.06483],
                                [-122.29629, 48.06368],
                                [-122.29453, 48.06231],
                                [-122.2935, 48.0617],
                                [-122.29119, 48.05514],
                                [-122.29149, 48.05367],
                                [-122.29016, 48.05218],
                                [-122.2823, 48.0494],
                                [-122.26943, 48.04573],
                                [-122.27115, 48.04366],
                                [-122.29431, 48.05258],
                                [-122.33276, 48.07601]
                            ]]
                        }
                    }
                };

                // Add custom polygon layers
                Object.entries(customAreaPolygons).forEach(([areaName, geoJson]) => {
                    // Find matching data for this custom area
                    let areaData = { total: 0, surveys: 0 };
                    if (dataMap[areaName]) {
                        areaData = dataMap[areaName];
                    }

                    const intensity = Math.min(areaData.total / maxCatch, 1);
                    const fillOpacity = 0.3 + intensity * 0.5;

                    const customLayer = L.geoJSON(geoJson, {
                        style: function(feature) {
                            return {
                                color: '#3182ce',
                                weight: 2,
                                opacity: 0.8,
                                fillColor: '#3182ce',
                                fillOpacity: fillOpacity
                            };
                        },
                        onEachFeature: function(feature, layer) {
                            // Store reference for selection tracking
                            layer.areaName = areaName;

                            // Hover effects
                            layer.on('mouseover', function(e) {
                                const isSelected = selectedAreaLayers.has(layer);
                                if (!isSelected) {
                                    layer.setStyle({
                                        fillColor: '#facc15',
                                        fillOpacity: 0.6
                                    });
                                }
                            });

                            layer.on('mouseout', function(e) {
                                const isSelected = selectedAreaLayers.has(layer);
                                if (!isSelected) {
                                    layer.setStyle({
                                        fillColor: '#3182ce',
                                        fillOpacity: fillOpacity
                                    });
                                }
                            });

                            // Click to toggle selection
                            layer.on('click', function(e) {
                                const catchAreaSelect = document.getElementById('catchArea');

                                let optionFound = false;
                                let isCurrentlySelected = false;

                                for (let i = 0; i < catchAreaSelect.options.length; i++) {
                                    if (catchAreaSelect.options[i].value === areaName) {
                                        optionFound = true;
                                        isCurrentlySelected = catchAreaSelect.options[i].selected;
                                        catchAreaSelect.options[i].selected = !isCurrentlySelected;
                                        break;
                                    }
                                }

                                if (optionFound) {
                                    if (!isCurrentlySelected) {
                                        selectedAreaLayers.add(layer);
                                        layer.setStyle({
                                            color: '#f59e0b',
                                            weight: 4,
                                            fillColor: '#fbbf24',
                                            fillOpacity: 0.7
                                        });
                                        layer.bringToFront();
                                    } else {
                                        selectedAreaLayers.delete(layer);
                                        layer.setStyle({
                                            color: '#3182ce',
                                            weight: 2,
                                            fillColor: '#3182ce',
                                            fillOpacity: fillOpacity
                                        });
                                    }
                                    applyFilters();
                                }
                            });

                            // Popup
                            const popupContent = `
                                <div style="font-family: sans-serif;">
                                    <h3 style="margin: 0 0 8px 0; color: #2d3748; font-size: 1.1em;">
                                        ${areaName}
                                    </h3>
                                    <div style="border-top: 1px solid #e2e8f0; padding-top: 8px;">
                                        <p style="margin: 4px 0;"><strong>Total Catch:</strong> ${Math.round(areaData.total).toLocaleString()}</p>
                                        <p style="margin: 4px 0;"><strong>Surveys:</strong> ${areaData.surveys.toLocaleString()}</p>
                                    </div>
                                    <p style="margin: 8px 0 4px 0; font-size: 0.85em; color: #718096;">
                                        <em>Custom boundary (not in WDFW GIS)</em>
                                    </p>
                                </div>
                            `;
                            layer.bindPopup(popupContent);
                        }
                    }).addTo(map);

                    // Bring custom layer to front so it's clickable above GIS layers
                    customLayer.bringToFront();

                    // Store reference
                    if (!window.customAreaLayers) {
                        window.customAreaLayers = {};
                    }
                    window.customAreaLayers[areaName] = customLayer;
                });


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

                    // Bring custom layers to front so they're above GIS layers
                    if (window.customAreaLayers) {
                        Object.values(window.customAreaLayers).forEach(layer => {
                            layer.bringToFront();
                        });
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