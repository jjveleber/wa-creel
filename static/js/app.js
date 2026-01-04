let charts = {};
        let map = null;
        let mapLayers = [];
        let marineAreasLayer = null; // Store the Esri feature layer
        let selectedAreaLayers = new Set(); // Track all selected areas
        let initialMapLoadComplete = false; // Prevent zoom reset on pan/zoom
        let areaNumberToDbName = {}; // Mapping from area number to database area name
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

                // Build mapping from area number to database area name
                areaNumberToDbName = {};
                options.areas.forEach(area => {
                    // Extract area number from names like "Area 4, Eastern portion"
                    const match = area.match(/^Area\s+(\d+),/);
                    if (match) {
                        const areaNum = match[1];
                        areaNumberToDbName[areaNum] = area;
                    }
                });
                console.log("✅ Built area number mapping:", Object.keys(areaNumberToDbName).length, "areas");
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

        // ==========================================
        // FILTER PERSISTENCE (localStorage)
        // ==========================================

        function saveFilterSettings() {
            try {
                const filters = {
                    yearStart: document.getElementById('yearStart').value,
                    yearEnd: document.getElementById('yearEnd').value,
                    catchAreas: getSelectValues(document.getElementById('catchArea')),
                    species: getSelectValues(document.getElementById('species')),
                    timeUnit: document.getElementById('timeUnit').value,
                    timestamp: new Date().toISOString()
                };

                localStorage.setItem('wdfw_creel_filters', JSON.stringify(filters));
                console.log('✅ Saved filter settings:', filters);
            } catch (error) {
                console.error('Error saving filter settings:', error);
            }
        }

        function loadFilterSettings() {
            try {
                const saved = localStorage.getItem('wdfw_creel_filters');
                if (!saved) {
                    console.log('No saved filter settings found');
                    return null;
                }

                const filters = JSON.parse(saved);
                console.log('✅ Loaded filter settings:', filters);
                return filters;
            } catch (error) {
                console.error('Error loading filter settings:', error);
                return null;
            }
        }

        function applyFilterSettings(filters) {
            if (!filters) return;

            try {
                // Apply year start
                if (filters.yearStart) {
                    const yearStartSelect = document.getElementById('yearStart');
                    for (let i = 0; i < yearStartSelect.options.length; i++) {
                        if (yearStartSelect.options[i].value === filters.yearStart) {
                            yearStartSelect.selectedIndex = i;
                            break;
                        }
                    }
                }

                // Apply year end
                if (filters.yearEnd) {
                    const yearEndSelect = document.getElementById('yearEnd');
                    for (let i = 0; i < yearEndSelect.options.length; i++) {
                        if (yearEndSelect.options[i].value === filters.yearEnd) {
                            yearEndSelect.selectedIndex = i;
                            break;
                        }
                    }
                }

                // Apply catch area selections
                const catchAreaSelect = document.getElementById('catchArea');
                if (filters.catchAreas && filters.catchAreas.length > 0) {
                    for (let i = 0; i < catchAreaSelect.options.length; i++) {
                        const option = catchAreaSelect.options[i];
                        option.selected = filters.catchAreas.includes(option.value);
                    }
                }

                // Apply species selections
                const speciesSelect = document.getElementById('species');
                if (filters.species && filters.species.length > 0) {
                    for (let i = 0; i < speciesSelect.options.length; i++) {
                        const option = speciesSelect.options[i];
                        option.selected = filters.species.includes(option.value);
                    }
                }

                // Apply time unit
                if (filters.timeUnit) {
                    document.getElementById('timeUnit').value = filters.timeUnit;
                }

                console.log('✅ Applied saved filters');

                // Trigger filter update to reload data
                applyFilters();

            } catch (error) {
                console.error('Error applying filter settings:', error);
            }
        }

        function clearFilterSettings() {
            try {
                localStorage.removeItem('wdfw_creel_filters');
                console.log('✅ Cleared saved filter settings');
            } catch (error) {
                console.error('Error clearing filter settings:', error);
            }
        }

        function updateMapSelection() {
            // Update map layer styling based on currently selected areas in dropdown
            if (!map || !mapLayers || mapLayers.length === 0) {
                console.log('⏳ Map not ready yet for selection update');
                return;
            }

            try {
                const catchAreaSelect = document.getElementById('catchArea');
                if (!catchAreaSelect) return;

                const selectedAreas = Array.from(catchAreaSelect.selectedOptions).map(opt => opt.value);
                console.log('🗺️ Updating map selection:', selectedAreas);

                // Clear selection tracking
                selectedAreaLayers.clear();

                // Update WDFW layers
                mapLayers.forEach(layer => {
                    const props = layer.feature.properties;
                    const gisAreaNumber = props.maNumber;
                    const gisAreaName = props.maName;

                    // Find matching database area name
                    let dbAreaName = null;
                    if (window.mapDataLookup && window.mapDataLookup[gisAreaName]) {
                        dbAreaName = gisAreaName;
                    } else {
                        const searchPattern = `Area ${gisAreaNumber},`;
                        for (const dbName of Object.keys(window.mapDataLookup || {})) {
                            if (dbName.startsWith(searchPattern)) {
                                dbAreaName = dbName;
                                break;
                            }
                        }
                    }

                    // Fallback: use canonical mapping if not found in current data
                    if (!dbAreaName && gisAreaNumber && areaNumberToDbName[gisAreaNumber]) {
                        dbAreaName = areaNumberToDbName[gisAreaNumber];
                    }

                    // Check if selected
                    const isSelected = dbAreaName && selectedAreas.includes(dbAreaName);

                    // Update styling
                    if (isSelected) {
                        selectedAreaLayers.add(layer);
                        layer.setStyle({
                            color: '#f59e0b',
                            weight: 4,
                            opacity: 1,
                            fillColor: '#fbbf24',
                            fillOpacity: 0.7
                        });
                    } else {
                        // Get data for intensity-based coloring
                        let areaData = { total: 0, surveys: 0 };
                        if (window.mapDataLookup && dbAreaName && window.mapDataLookup[dbAreaName]) {
                            areaData = window.mapDataLookup[dbAreaName];
                        }
                        const maxCatch = Math.max(...Object.values(window.mapDataLookup || {}).map(d => d.total || 0), 1);
                        const intensity = Math.min(areaData.total / maxCatch, 1);
                        const fillOpacity = 0.3 + intensity * 0.5;

                        layer.setStyle({
                            color: '#3182ce',
                            weight: 2,
                            opacity: 0.8,
                            fillColor: '#60a5fa',
                            fillOpacity: fillOpacity
                        });
                    }
                });

                // Update custom area layers
                if (window.customAreaLayers) {
                    Object.entries(window.customAreaLayers).forEach(([areaName, layerGroup]) => {
                        const isSelected = selectedAreas.includes(areaName);

                        layerGroup.eachLayer(function(layer) {
                            if (isSelected) {
                                selectedAreaLayers.add(layer);
                                layer.setStyle({
                                    color: '#f59e0b',
                                    weight: 4,
                                    fillColor: '#fbbf24',
                                    fillOpacity: 0.7
                                });
                            } else {
                                // Get data for intensity-based coloring
                                let areaData = { total: 0, surveys: 0 };
                                if (window.mapDataLookup && window.mapDataLookup[areaName]) {
                                    areaData = window.mapDataLookup[areaName];
                                }
                                const maxCatch = Math.max(...Object.values(window.mapDataLookup || {}).map(d => d.total || 0), 1);
                                const intensity = Math.min(areaData.total / maxCatch, 1);
                                const fillOpacity = 0.3 + intensity * 0.5;

                                layer.setStyle({
                                    color: '#3182ce',
                                    weight: 2,
                                    fillColor: '#3182ce',
                                    fillOpacity: fillOpacity
                                });
                            }
                        });
                    });
                }

                console.log('✅ Map selection updated');
            } catch (error) {
                console.error('Error updating map selection:', error);
            }
        }



        function applyFilters() {
            currentFilters = {
                year_start: document.getElementById('yearStart').value,
                year_end: document.getElementById('yearEnd').value,
                catch_area: getSelectValues(document.getElementById('catchArea')),
                species: getSelectValues(document.getElementById('species')),
                time_unit: document.getElementById('timeUnit').value || 'yearly'
            };

            saveFilterSettings();  // Save settings to localStorage
            // Track filter changes in Google Analytics
            if (typeof gtag !== 'undefined') {
                // Get actual filter values
                const speciesList = currentFilters.species.join(',') || 'none';
                const areasList = currentFilters.catch_area.slice(0, 5).join(',') || 'all_areas'; // Limit to first 5 for parameter size
                const yearRange = (currentFilters.year_start || 'all') + '-' + (currentFilters.year_end || 'all');

                gtag('event', 'filter_change', {
                    // Year range
                    'year_start': currentFilters.year_start || 'all',
                    'year_end': currentFilters.year_end || 'all',
                    'year_range': yearRange,

                    // Species details
                    'species_selected': speciesList,
                    'species_count': currentFilters.species.length,

                    // Area details
                    'areas_selected': areasList,
                    'area_count': currentFilters.catch_area.length,

                    // Time unit
                    'time_unit': currentFilters.time_unit,

                    // Common combinations for quick analysis
                    'has_chinook': currentFilters.species.includes('chinook'),
                    'has_coho': currentFilters.species.includes('coho'),
                    'single_species': currentFilters.species.length === 1,
                    'all_salmon': currentFilters.species.length === 5 &&
                                  currentFilters.species.includes('chinook') &&
                                  currentFilters.species.includes('coho') &&
                                  currentFilters.species.includes('chum') &&
                                  currentFilters.species.includes('pink') &&
                                  currentFilters.species.includes('sockeye')
                });
            }

            loadData();  // Load updated data
        }

        function resetFilters() {
            clearFilterSettings();  // Clear saved filter settings from localStorage

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

            // Track filter reset
            if (typeof gtag !== 'undefined') {
                gtag('event', 'filter_reset', {
                    'action': 'reset_to_defaults'
                });
            }
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

            // Check if Leaflet is loaded
            if (typeof L === 'undefined') {
                console.error('Leaflet library not loaded!');
                document.getElementById('map').innerHTML = '<div style="padding: 20px; text-align: center; color: #e53e3e;">Error: Leaflet library failed to load. Please refresh the page.</div>';
                return;
            }

            try {
                // Initialize map if not already created
                if (!map) {

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

                    // Create custom panes for layer separation (prevents hover flicker)
                    map.createPane('wdfwPane');
                    map.createPane('customAreasPane');

                    // Set z-indexes (higher = on top, default overlayPane is 400)
                    map.getPane('wdfwPane').style.zIndex = 400;         // WDFW areas on bottom
                    map.getPane('customAreasPane').style.zIndex = 450;  // Custom areas on top

                    // Enable pointer events on both panes
                    map.getPane('wdfwPane').style.pointerEvents = 'auto';  // Enable clicks on WDFW areas
                    map.getPane('customAreasPane').style.pointerEvents = 'auto';

                }

                // Create a map of catch data by area name
                window.mapDataLookup = {}; const dataMap = window.mapDataLookup;
                data.forEach(d => {
                    dataMap[d.area] = d;
                });

                // Find max catch for color scaling
                const maxCatch = Math.max(...data.map(d => d.total), 1);

                // Helper function to calculate style
                function getStyleForFeature(feature, isSelected = false) {
                    const props = feature.properties;
                    const gisAreaNumber = props.maNumber;
                    const gisAreaName = props.maName;

                    // Find matching catch data
                    let areaData = { total: 0, surveys: 0 };
                    let matchedDbName = null;

                    // Try exact name match first
                    if (window.mapDataLookup && window.mapDataLookup[gisAreaName]) {
                        areaData = window.mapDataLookup[gisAreaName];
                        matchedDbName = gisAreaName;
                    } else {
                        // Try pattern matching
                        const searchPattern = `Area ${gisAreaNumber},`;
                        for (const [dbName, dbData] of Object.entries(window.mapDataLookup || {})) {
                            if (dbName.startsWith(searchPattern)) {
                                areaData = dbData;
                                matchedDbName = dbName;
                                break;
                            }
                        }
                    }

                    const intensity = Math.min(areaData.total / maxCatch, 1);
                    const fillOpacity = 0.3 + intensity * 0.5;

                    if (isSelected) {
                        return {
                            color: '#f59e0b',
                            weight: 4,
                            opacity: 1,
                            fillColor: '#fbbf24',
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

                // If layer already exists, update styling without recreating
                if (marineAreasLayer && mapLayers.length > 0) {

                    // Get selected areas from filter dropdown
                    const catchAreaSelect = document.getElementById('catchArea');
                    const selectedAreas = Array.from(catchAreaSelect.selectedOptions).map(opt => opt.value);

                    // Clear and rebuild selection tracking
                    selectedAreaLayers.clear();

                    // Update each existing layer
                    mapLayers.forEach(layer => {
                        const props = layer.feature.properties;
                        const gisAreaNumber = props.maNumber;
                        const gisAreaName = props.maName;

                        // Find matching database area
                        let dbAreaName = null;
                        let areaData = { total: 0, surveys: 0 };

                        // Try exact name match first
                        if (window.mapDataLookup && window.mapDataLookup[gisAreaName]) {
                            dbAreaName = gisAreaName;
                            areaData = window.mapDataLookup[gisAreaName];
                        } else {
                            // Try pattern matching
                            const searchPattern = `Area ${gisAreaNumber},`;
                            for (const [dbName, dbData] of Object.entries(window.mapDataLookup || {})) {
                                if (dbName.startsWith(searchPattern)) {
                                    dbAreaName = dbName;
                                    areaData = dbData;
                                    break;
                                }
                            }
                        }

                        // Check if this area is selected
                        const isSelected = dbAreaName && selectedAreas.includes(dbAreaName);

                        // Update styling
                        const style = getStyleForFeature(layer.feature, isSelected);
                        layer.setStyle(style);

                        // Track selected areas
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

                    // Update custom area layers
                    if (window.customAreaLayers) {
                        Object.entries(window.customAreaLayers).forEach(([areaName, layerGroup]) => {
                            const isSelected = selectedAreas.includes(areaName);

                            layerGroup.eachLayer(function(layer) {
                                let areaData = { total: 0, surveys: 0 };
                                if (window.mapDataLookup && window.mapDataLookup[areaName]) {
                                    areaData = window.mapDataLookup[areaName];
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
                        });
                    }

                    return; // Exit - layer updated, no need to recreate
                }

                // Create layer for the first time
                mapLayers = [];

                // Load marine areas from static GeoJSON file
                fetch('/static/data/wdfw_marine_areas.json')
                    .then(response => {
                        if (!response.ok) {
                            throw new Error('Failed to load marine areas');
                        }
                        return response.json();
                    })
                    .then(geojsonData => {
                        marineAreasLayer = L.geoJSON(geojsonData, {
                            pane: 'wdfwPane',
                            style: getStyleForFeature,
                            onEachFeature: function(feature, layer) {
                                const props = feature.properties;
                                const gisAreaNumber = props.maNumber;

                                // Find matching database area
                                let dbAreaName = null;
                                let areaData = { total: 0, surveys: 0 };

                                // First, try exact name match
                                const gisAreaName = props.maName;
                                if (window.mapDataLookup && window.mapDataLookup[gisAreaName]) {
                                    dbAreaName = gisAreaName;
                                    areaData = window.mapDataLookup[gisAreaName];
                                } else {
                                    // If no exact match, try pattern matching
                                    const searchPattern = `Area ${gisAreaNumber},`;
                                    for (const [dbName, dbData] of Object.entries(window.mapDataLookup || {})) {
                                        if (dbName.startsWith(searchPattern)) {
                                            dbAreaName = dbName;
                                            areaData = dbData;
                                            break;
                                        }
                                    }
                                }

                                // Fallback: use canonical mapping from area number to database name
                                if (!dbAreaName && gisAreaNumber) {
                                    if (areaNumberToDbName[gisAreaNumber]) {
                                        // Use exact database name from mapping
                                        dbAreaName = areaNumberToDbName[gisAreaNumber];
                                    } else if (gisAreaName) {
                                        // Last resort: construct from GIS properties
                                        dbAreaName = `Area ${gisAreaNumber}, ${gisAreaName}`;
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
                                });

                                layer.on('mouseout', function(e) {
                                    const isSelected = selectedAreaLayers.has(layer);
                                    const style = getStyleForFeature(feature, isSelected);
                                    layer.setStyle(style);
                                });

                                // Click to toggle area selection
                                layer.on('click', function(e) {
                                    if (dbAreaName) {
                                        const catchAreaSelect = document.getElementById('catchArea');

                                        let optionFound = false;
                                        let isCurrentlySelected = false;

                                        for (let i = 0; i < catchAreaSelect.options.length; i++) {
                                            if (catchAreaSelect.options[i].value === dbAreaName) {
                                                optionFound = true;
                                                isCurrentlySelected = catchAreaSelect.options[i].selected;
                                                catchAreaSelect.options[i].selected = !isCurrentlySelected;
                                                break;
                                            }
                                        }

                                        if (optionFound) {
                                            if (!isCurrentlySelected) {
                                                selectedAreaLayers.add(layer);
                                                const selectedStyle = getStyleForFeature(feature, true);
                                                layer.setStyle(selectedStyle);
                                            } else {
                                                selectedAreaLayers.delete(layer);
                                                const unselectedStyle = getStyleForFeature(feature, false);
                                                layer.setStyle(unselectedStyle);
                                            }

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

                        console.log('✅ Loaded marine areas from static GeoJSON file');

                        // After loading marine areas, fit bounds
                        if (!initialMapLoadComplete && mapLayers.length > 0) {
                            const group = L.featureGroup(mapLayers);
                            const bounds = group.getBounds();
                            if (bounds.isValid()) {
                                map.fitBounds(bounds, { padding: [20, 20] });
                                initialMapLoadComplete = true;
                            }
                        }

                        // Update map selection to match any saved filters
                        updateMapSelection();
                    })
                    .catch(error => {
                        console.error('Error loading marine areas:', error);
                        document.getElementById('map').innerHTML = '<div style="padding: 20px; text-align: center; color: #e53e3e;">Error loading marine areas. Please refresh the page.</div>';
                    });

                // Add custom area polygons for areas not in WDFW GIS layer
                Object.entries(customAreaPolygons).forEach(([areaName, geoJson]) => {
                    let areaData = { total: 0, surveys: 0 };
                    if ((window.mapDataLookup || {})[areaName]) {
                        areaData = window.mapDataLookup[areaName];
                    }

                    const intensity = Math.min(areaData.total / maxCatch, 1);
                    const fillOpacity = 0.3 + intensity * 0.5;

                    const customLayer = L.geoJSON(geoJson, {
                        pane: 'customAreasPane',
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
                            layer.areaName = areaName;

                            layer.on('mouseover', function(e) {
                                L.DomEvent.stopPropagation(e);
                                const isSelected = selectedAreaLayers.has(layer);
                                if (!isSelected) {
                                    layer.setStyle({
                                        fillColor: '#facc15',
                                        fillOpacity: 0.6
                                    });
                                }
                            });

                            layer.on('mouseout', function(e) {
                                L.DomEvent.stopPropagation(e);
                                const isSelected = selectedAreaLayers.has(layer);
                                if (!isSelected) {
                                    layer.setStyle({
                                        fillColor: '#3182ce',
                                        fillOpacity: fillOpacity
                                    });
                                }
                            });

                            layer.on('click', function(e) {
                                L.DomEvent.stopPropagation(e);
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
                                        // Track map area selection
                                        if (typeof gtag !== 'undefined') {
                                            gtag('event', 'map_area_selected', {
                                                'area': areaName,
                                                'action': 'select'
                                            });
                                        }
                                        selectedAreaLayers.add(layer);
                                        layer.setStyle({
                                            color: '#f59e0b',
                                            weight: 4,
                                            fillColor: '#fbbf24',
                                            fillOpacity: 0.7
                                        });
                                    } else {
                                        // Track map area deselection
                                        if (typeof gtag !== 'undefined') {
                                            gtag('event', 'map_area_selected', {
                                                'area': areaName,
                                                'action': 'deselect'
                                            });
                                        }
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

                    if (!window.customAreaLayers) {
                        window.customAreaLayers = {};
                    }
                    window.customAreaLayers[areaName] = customLayer;
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

            if (charts.trend) {
                charts.trend.destroy();
            }

            const speciesColors = {
                'chinook': { border: '#e53e3e', bg: 'rgba(229, 62, 62, 0.1)' },
                'coho': { border: '#3182ce', bg: 'rgba(49, 130, 206, 0.1)' },
                'chum': { border: '#805ad5', bg: 'rgba(128, 90, 213, 0.1)' },
                'pink': { border: '#ed64a6', bg: 'rgba(237, 100, 166, 0.1)' },
                'sockeye': { border: '#38a169', bg: 'rgba(56, 161, 105, 0.1)' },
                'lingcod': { border: '#d69e2e', bg: 'rgba(214, 158, 46, 0.1)' },
                'halibut': { border: '#dd6b20', bg: 'rgba(221, 107, 32, 0.1)' }
            };

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

        async function checkForUpdates() {
            try {
                const response = await fetch('/api/update');
                const data = await response.json();

                if (data.updated) {
                    console.log('✅ Data updated:', data.message);
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
            checkForUpdates();

            await Promise.all([
                loadFilterOptions(),
                loadData()
            ]);

            // Load and apply saved filter settings
            const savedFilters = loadFilterSettings();
            if (savedFilters) {
                applyFilterSettings(savedFilters);
            }
        }

        init();