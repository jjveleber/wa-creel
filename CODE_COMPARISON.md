# Code Comparison: Old vs New Map Implementation

## Library Import

### OLD (index.py - Line 128-130):
```html
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"
    integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo="
    crossorigin=""></script>
<style>
```

### NEW (index.py - Line 128-133):
```html
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"
    integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo="
    crossorigin=""></script>
<!-- Esri Leaflet for loading WDFW GIS data -->
<script src="https://unpkg.com/esri-leaflet@2.5.3/dist/esri-leaflet.js"></script>
<style>
```

**Change**: Added Esri Leaflet library import

---

## Polygon Data Source

### OLD - Hardcoded Rectangles:
```javascript
// Define more accurate boundaries for Puget Sound catch areas
const areaBoundaries = {
    'Area 13, South Puget Sound': [ // South of Tacoma Narrows Bridge
        [47.27, -122.90], [47.27, -122.40], [47.05, -122.60], [47.00, -122.90]
    ],
    'Area 11, Tacoma-Vashon Island': [ // Vashon north tip to Tacoma Narrows
        [47.27, -122.70], [47.27, -122.35], [47.42, -122.35], [47.50, -122.50], [47.50, -122.70]
    ],
    // ... more hardcoded coordinates ...
};

// Manually create polygons
Object.entries(areaBoundaries).forEach(([areaName, coords]) => {
    const polygon = L.polygon(coords, {
        color: '#3182ce',
        fillColor: color,
        fillOpacity: 0.6,
        weight: 2
    }).addTo(map);
});
```

### NEW - Dynamic GIS Loading:
```javascript
// Mapping from database area names to GIS Marine Area names
const areaNameMap = {
    'Area 13, South Puget Sound': 'Area 13',
    'Area 11, Tacoma-Vashon Island': 'Area 11',
    // ... mappings only, no coordinates ...
};

// Load WDFW Marine Area polygons using Esri Leaflet
const WDFW_MAPSERVER_URL = "https://geodataservices.wdfw.wa.gov/arcgis/rest/services/ApplicationServices/Marine_Areas/MapServer";
const LAYER_INDEX = 3; // Marine Area Polygons layer

const marineAreasLayer = L.esri.featureLayer({
    url: WDFW_MAPSERVER_URL + '/' + LAYER_INDEX,
    
    style: function(feature) {
        // Dynamic styling based on catch data
        const props = feature.properties;
        const gisAreaName = props.maName || props.maNumber;
        const dbAreaName = reverseAreaMap[gisAreaName];
        const areaData = dataMap[dbAreaName] || { total: 0 };
        
        const intensity = Math.min(areaData.total / maxCatch, 1);
        return {
            color: '#3182ce',
            weight: 2,
            fillColor: '#60a5fa',
            fillOpacity: 0.3 + intensity * 0.5
        };
    },
    
    onEachFeature: function(feature, layer) {
        // Add interactions, popups, etc.
    }
}).addTo(map);
```

**Changes**: 
- No hardcoded coordinates
- Fetches real polygon shapes from WDFW's GIS server
- Uses official Marine Area boundaries
- Includes metadata (WAC codes, area names, etc.)

---

## Data Visualization Approach

### OLD:
```javascript
// Static color calculation
const intensity = Math.min(areaData.total / maxCatch, 1);
const color = `rgba(49, 130, 206, ${0.3 + intensity * 0.6})`;

const polygon = L.polygon(coords, {
    color: '#3182ce',
    fillColor: color,
    fillOpacity: 0.6,
    weight: 2
}).addTo(map);
```

### NEW:
```javascript
// Dynamic style function applied to each GIS feature
style: function(feature) {
    const props = feature.properties;
    const gisAreaName = props.maName || props.maNumber;
    const dbAreaName = reverseAreaMap[gisAreaName] || 
                      reverseAreaMap['Area ' + props.maNumber];
    const areaData = dataMap[dbAreaName] || { total: 0, surveys: 0 };
    
    // Color intensity based on catch
    const intensity = Math.min(areaData.total / maxCatch, 1);
    const fillOpacity = 0.3 + intensity * 0.5;
    
    return {
        color: '#3182ce',
        weight: 2,
        opacity: 0.8,
        fillColor: '#60a5fa',
        fillOpacity: fillOpacity
    };
}
```

**Change**: More sophisticated mapping between database and GIS names, applied dynamically to each feature

---

## Error Handling

### OLD:
```javascript
if (typeof L === 'undefined') {
    console.error('Leaflet library not loaded!');
    document.getElementById('map').innerHTML = '<div>Error...</div>';
    return;
}
```

### NEW:
```javascript
if (typeof L === 'undefined') {
    console.error('Leaflet library not loaded!');
    document.getElementById('map').innerHTML = '<div>Error...</div>';
    return;
}

// NEW: Also check for Esri Leaflet
if (typeof L.esri === 'undefined') {
    console.error('Esri Leaflet library not loaded!');
    document.getElementById('map').innerHTML = '<div>Error: Esri Leaflet library required...</div>';
    return;
}
```

**Change**: Added validation for Esri Leaflet library

---

## Loading Events

### OLD:
```javascript
// No loading events - polygons added synchronously
setTimeout(() => {
    if (map) {
        map.invalidateSize();
        if (mapLayers.length > 0) {
            const group = L.featureGroup(mapLayers);
            map.fitBounds(group.getBounds(), { padding: [20, 20] });
        }
    }
}, 300);
```

### NEW:
```javascript
// Handle async loading events
marineAreasLayer.on('load', function(e) {
    console.log('Marine areas loaded successfully');
    
    // Fit map to show all polygons
    if (mapLayers.length > 0) {
        const group = L.featureGroup(mapLayers);
        map.fitBounds(group.getBounds(), { padding: [20, 20] });
    }
});

marineAreasLayer.on('error', function(e) {
    console.error('Error loading marine areas:', e);
    document.getElementById('map').innerHTML = 
        '<div>Error loading WDFW marine area data. Check console for details.</div>';
});
```

**Change**: Proper async event handling for data loading

---

## Visual Comparison

### OLD Map (Hardcoded):
```
┌─────────────────────────┐
│  [Rough rectangles]     │
│  ┌──┐  ┌──┐            │
│  │13│  │11│  ┌──┐      │
│  └──┘  └──┘  │10│      │
│               └──┘      │
│  Approximate shapes     │
│  Limited accuracy       │
└─────────────────────────┘
```

### NEW Map (GIS):
```
┌─────────────────────────┐
│  [Accurate shapes]      │
│  ╭─╮  ╭──╮             │
│  │13│ ╱│11│╲  ╭─╮      │
│  ╰─╯ ╲ ╰──╯ ╱ │10│     │
│       ╲    ╱   ╰─╯     │
│  Official WDFW shapes   │
│  Professional quality   │
└─────────────────────────┘
```

---

## Summary of Improvements

| Aspect | Old | New |
|--------|-----|-----|
| **Data Source** | Hardcoded coordinates | WDFW GIS server |
| **Accuracy** | Approximate rectangles | Official boundaries |
| **Maintainability** | Manual updates needed | Auto-updates |
| **Metadata** | None | WAC codes, area info |
| **Loading** | Synchronous | Async with events |
| **Polygon Count** | 10 areas (hardcoded) | All WA Marine Areas |
| **Shape Quality** | Basic rectangles | Complex real shapes |
| **Professional** | ⭐⭐ | ⭐⭐⭐⭐⭐ |

---

## What Stayed The Same

✓ Map interactions (hover, click, popup)
✓ Data filtering functionality  
✓ Color-coding by catch intensity
✓ Integration with dashboard filters
✓ Overall visual style and layout
✓ Chart.js visualizations

The core functionality is preserved - only the polygon source changed from static to dynamic!
