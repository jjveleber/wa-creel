"""
Google Cloud Storage operations for database persistence
"""
import os

try:
    from google.cloud import storage
    GCS_AVAILABLE = True
except ImportError:
    GCS_AVAILABLE = False
    print("Warning: google-cloud-storage not installed. Database persistence disabled.")


def download_database_from_gcs(bucket_name, db_path):
    """Download database from Google Cloud Storage if it exists"""
    if not GCS_AVAILABLE or not bucket_name:
        return False
    
    try:
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
    if not GCS_AVAILABLE or not bucket_name:
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
