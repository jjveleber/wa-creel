"""
Configuration management for WDFW Creel Dashboard
"""
import os


class Config:
    """Application configuration"""
    
    # Server configuration
    PORT = int(os.environ.get("PORT", 8080))
    HOST = "0.0.0.0"
    
    # Database configuration
    DB_DIR = "wdfw_creel_data"
    DB_PATH = os.path.join(DB_DIR, "creel_data.db")
    
    # Google Cloud Storage configuration
    GCS_BUCKET_NAME = os.environ.get("GCS_BUCKET_NAME")
    GCS_DB_FILENAME = "creel_data.db"
    
    # Auto-update configuration
    UPDATE_INTERVAL_HOURS = 24
    
    # WDFW API configuration
    WDFW_MAPSERVER_URL = "https://geodataservices.wdfw.wa.gov/arcgis/rest/services/ApplicationServices/Marine_Areas/MapServer"
    
    @classmethod
    def ensure_directories(cls):
        """Ensure required directories exist"""
        os.makedirs(cls.DB_DIR, exist_ok=True)
