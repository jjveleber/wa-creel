#!/usr/bin/env python3
"""
Fetch WDFW Marine Areas from ArcGIS MapServer and save as static GeoJSON
Run this locally to generate the static file
"""
import requests
import json

WDFW_MAPSERVER_URL = "https://geodataservices.wdfw.wa.gov/arcgis/rest/services/ApplicationServices/Marine_Areas/MapServer"
LAYER_INDEX = 3

def fetch_marine_areas():
    """Fetch all marine areas as GeoJSON"""
    query_url = f"{WDFW_MAPSERVER_URL}/{LAYER_INDEX}/query"
    
    query_params = {
        'where': '1=1',  # Get all features
        'outFields': '*',
        'f': 'geojson',
        'returnGeometry': 'true'
    }
    
    print("Fetching WDFW Marine Areas...")
    response = requests.get(query_url, params=query_params)
    response.raise_for_status()
    
    geojson_data = response.json()
    
    print(f"✅ Fetched {len(geojson_data.get('features', []))} marine areas")
    
    # Show sample
    if geojson_data.get('features'):
        sample = geojson_data['features'][0]
        print("\nSample properties:")
        for key, value in list(sample.get('properties', {}).items())[:5]:
            print(f"  {key}: {value}")
    
    return geojson_data

def save_geojson(data, filename='wdfw_marine_areas.json'):
    """Save GeoJSON to file"""
    with open(filename, 'w') as f:
        json.dump(data, f, indent=2)
    
    file_size = len(json.dumps(data))
    print(f"\n✅ Saved to {filename}")
    print(f"📊 File size: {file_size:,} bytes ({file_size/1024:.1f} KB)")
    print(f"📍 Features: {len(data.get('features', []))}")

if __name__ == '__main__':
    try:
        geojson_data = fetch_marine_areas()
        save_geojson(geojson_data, 'static/data/wdfw_marine_areas.json')
        print("\n🎉 Success! You can now use this static file instead of the API.")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("\nMake sure you run this from your project root directory.")
