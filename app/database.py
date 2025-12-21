"""
Database operations for WDFW Creel Dashboard
"""
import sqlite3
import os
from datetime import datetime
from .config import Config


def get_db_connection():
    """Get a connection to the SQLite database"""
    return sqlite3.connect(Config.DB_PATH)


def ensure_metadata_table(conn):
    """Ensure metadata table exists in database"""
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS metadata (
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_at TEXT
        )
    """)
    conn.commit()


def get_last_update_time():
    """Get the timestamp of the last data update from database"""
    conn = None
    try:
        conn = get_db_connection()
        ensure_metadata_table(conn)
        cursor = conn.cursor()
        
        cursor.execute("SELECT value FROM metadata WHERE key = 'last_update'")
        row = cursor.fetchone()
        
        if row:
            return datetime.fromisoformat(row[0])
        return None
    except Exception as e:
        print(f"Error getting last update time: {e}")
        return None
    finally:
        if conn:
            conn.close()


def set_last_update_time():
    """Record the current time as the last update time in database"""
    conn = None
    try:
        conn = get_db_connection()
        ensure_metadata_table(conn)
        cursor = conn.cursor()
        
        now = datetime.now().isoformat()
        cursor.execute("""
            INSERT OR REPLACE INTO metadata (key, value, updated_at)
            VALUES ('last_update', ?, ?)
        """, (now, now))
        conn.commit()
    except Exception as e:
        print(f"Warning: Could not write update timestamp: {e}")
    finally:
        if conn:
            conn.close()


def get_species_columns(params):
    """
    Get species columns to aggregate based on filter
    
    Args:
        params: Query parameters dict with optional 'species' key
        
    Returns:
        str: SQL expression for summing species columns
    """
    if 'species' not in params:
        return "chinook + coho + chum + pink + sockeye"
    
    species_list = [s for s in params['species'] if s and s != 'all']
    
    if not species_list or 'all' in params.get('species', []):
        # Return all salmon species
        return "chinook + coho + chum + pink + sockeye"
    else:
        # Return sum of selected species
        return ' + '.join([s.lower() for s in species_list])


def get_species_list(params):
    """
    Get list of species for trend/breakdown analysis
    
    Args:
        params: Query parameters dict with optional 'species' key
        
    Returns:
        list: List of species names
    """
    if 'species' not in params:
        return ['chinook', 'coho', 'chum', 'pink', 'sockeye']
    
    species_list = [s for s in params['species'] if s and s != 'all']
    
    if not species_list or 'all' in params.get('species', []):
        return ['chinook', 'coho', 'chum', 'pink', 'sockeye']
    else:
        return [s.lower() for s in species_list]


def build_where_clause(params):
    """
    Build WHERE clause from query parameters
    
    Args:
        params: Query parameters dict
        
    Returns:
        tuple: (where_clause_string, query_params_list)
    """
    conditions = []
    query_params = []
    
    # Year range filter
    if 'year_start' in params:
        year_start = params['year_start'][0] if isinstance(params['year_start'], list) else params['year_start']
        conditions.append("substr(sample_date, -4) >= ?")
        query_params.append(year_start)
    
    if 'year_end' in params:
        year_end = params['year_end'][0] if isinstance(params['year_end'], list) else params['year_end']
        conditions.append("substr(sample_date, -4) <= ?")
        query_params.append(year_end)
    
    # Catch area filter (multi-select)
    if 'catch_area' in params:
        areas = params['catch_area'] if isinstance(params['catch_area'], list) else [params['catch_area']]
        areas = [a for a in areas if a]
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


def get_statistics(params=None):
    """
    Get aggregated statistics from database
    
    Args:
        params: Optional query parameters for filtering
        
    Returns:
        dict: Statistics including total catch, records, years, areas
    """
    if params is None:
        params = {}
    
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        where_clause, query_params = build_where_clause(params)
        
        # Get basic stats
        query = f"""
            SELECT 
                COUNT(*) as total_records,
                SUM(anglers) as total_anglers,
                SUM(chinook) as total_chinook,
                SUM(coho) as total_coho,
                SUM(chum) as total_chum,
                SUM(pink) as total_pink,
                SUM(sockeye) as total_sockeye,
                MIN(substr(sample_date, -4)) as min_year,
                MAX(substr(sample_date, -4)) as max_year
            FROM creel_records
            {where_clause}
        """
        
        cursor.execute(query, query_params)
        row = cursor.fetchone()
        
        # Count distinct catch areas
        area_query = f"""
            SELECT COUNT(DISTINCT catch_area) 
            FROM creel_records
            {where_clause}
            {"AND" if where_clause else "WHERE"} catch_area != ''
        """
        cursor.execute(area_query, query_params)
        areas_count = cursor.fetchone()[0] or 0
        
        # Calculate total catch from all species
        total_catch = sum([
            row[2] or 0,  # chinook
            row[3] or 0,  # coho
            row[4] or 0,  # chum
            row[5] or 0,  # pink
            row[6] or 0,  # sockeye
        ])
        
        return {
            'total_catch': round(total_catch),
            'surveys': row[0] or 0,
            'total_records': row[0] or 0,
            'total_anglers': round(row[1] or 0),
            'total_chinook': round(row[2] or 0),
            'total_coho': round(row[3] or 0),
            'min_year': row[7] or 'N/A',
            'max_year': row[8] or 'N/A',
            'areas': areas_count
        }
    except Exception as e:
        print(f"Error getting statistics: {e}")
        import traceback
        traceback.print_exc()
        return {
            'total_catch': 0,
            'surveys': 0,
            'min_year': None,
            'max_year': None,
            'areas': 0
        }
    finally:
        if conn:
            conn.close()


def get_catch_areas(params=None):
    """
    Get list of all catch areas with their total catch
    
    Args:
        params: Optional query parameters for filtering
        
    Returns:
        list: List of tuples (catch_area, total_catch)
    """
    if params is None:
        params = {}
    
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        where_clause, query_params = build_where_clause(params)
        species_columns = get_species_columns(params)
        
        query = f"""
            SELECT 
                catch_area,
                SUM({species_columns}) as total_catch
            FROM creel_records
            {where_clause}
            {"AND" if where_clause else "WHERE"} catch_area != ''
            GROUP BY catch_area
            ORDER BY total_catch DESC
        """
        
        cursor.execute(query, query_params)
        areas = cursor.fetchall()
        
        return areas
    except Exception as e:
        print(f"Error getting catch areas: {e}")
        import traceback
        traceback.print_exc()
        return []
    finally:
        if conn:
            conn.close()


def database_exists():
    """Check if database file exists"""
    return os.path.exists(Config.DB_PATH)
