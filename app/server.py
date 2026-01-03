"""
HTTP Server and Request Handlers for WDFW Creel Dashboard - Phase 2 Complete
"""
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
import json
import os
from urllib.parse import urlparse, parse_qs
from datetime import datetime, timedelta

from .config import Config
from . import database, gcs_storage

# Import data collector
try:
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from data_collector import WDFWCreelCollector
except ImportError:
    WDFWCreelCollector = None
    print("Warning: Could not import WDFWCreelCollector from data_collector.py")


class CreelDataHandler(SimpleHTTPRequestHandler):
    """HTTP request handler for creel data endpoints"""
    
    def do_GET(self):
        """Handle GET requests"""
        parsed_path = urlparse(self.path)
        path = parsed_path.path
        params = parse_qs(parsed_path.query)
        
        # API endpoints
        if path == '/api/stats':
            self.serve_statistics(params)
        elif path == '/api/areas':
            self.serve_areas(params)
        elif path == '/api/filter_options':
            self.serve_filter_options()
        elif path == '/api/yearly':
            self.serve_yearly_data(params)
        elif path == '/api/trend':
            self.serve_trend_data(params)
        elif path == '/api/species':
            self.serve_species_totals(params)
        elif path == '/api/monthly':
            self.serve_monthly_data(params)
        elif path == '/api/map_data':
            self.serve_map_data(params)
        elif path == '/api/update':
            self.serve_update_data()
        elif path == '/robots.txt':
            self.serve_robots()
        elif path == '/sitemap.xml':
            self.serve_sitemap()
        elif path == '/':
            self.serve_index()
        elif path.startswith('/static/'):
            self.serve_static_file(path)
        else:
            self.send_error(404, "Not Found")

    def serve_index(self):
        """Serve the main HTML page"""
        try:
            file_path = os.path.join('static', 'index.html')
            with open(file_path, 'r') as f:
                content = f.read()

            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(content.encode())
        except Exception as e:
            print(f"Error serving index: {e}")
            self.send_error(500, f"Server error: {str(e)}")

    def serve_static_file(self, path):
        """Serve static files (CSS, JS, images)"""
        try:
            file_path = path[1:]  # Remove leading '/'

            # Determine content type and if file is binary
            content_type = 'text/plain'
            is_binary = False

            if path.endswith('.css'):
                content_type = 'text/css'
            elif path.endswith('.js'):
                content_type = 'application/javascript'
            elif path.endswith('.ico'):
                content_type = 'image/x-icon'
                is_binary = True
            elif path.endswith('.png'):
                content_type = 'image/png'
                is_binary = True
            elif path.endswith('.jpg') or path.endswith('.jpeg'):
                content_type = 'image/jpeg'
                is_binary = True
            elif path.endswith('.svg'):
                content_type = 'image/svg+xml'
            elif path.endswith('.webmanifest'):
                content_type = 'application/manifest+json'
            elif path.endswith('.html'):
                content_type = 'text/html'

            # Open file in appropriate mode
            mode = 'rb' if is_binary else 'r'
            with open(file_path, mode) as f:
                content = f.read()

            self.send_response(200)
            self.send_header('Content-type', content_type)
            self.end_headers()

            # Write content (encode text, write binary as-is)
            if is_binary:
                self.wfile.write(content)
            else:
                self.wfile.write(content.encode())

        except FileNotFoundError:
            self.send_error(404, "File not found")
        except Exception as e:
            print(f"Error serving static file: {e}")
            self.send_error(500, f"Server error: {str(e)}")

    def serve_robots(self):
        """Serve robots.txt file"""
        try:
            file_path = os.path.join('static', 'robots.txt')
            with open(file_path, 'r') as f:
                content = f.read()

            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(content.encode())
        except FileNotFoundError:
            # Generate default robots.txt if file doesn't exist
            content = """User-agent: *
Allow: /

Sitemap: https://wa-creel.jeremyveleber.com/sitemap.xml
"""
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(content.encode())
        except Exception as e:
            print(f"Error serving robots.txt: {e}")
            self.send_error(500, f"Server error: {str(e)}")

    def serve_sitemap(self):
        """Serve sitemap.xml file"""
        try:
            file_path = os.path.join('static', 'sitemap.xml')
            with open(file_path, 'r') as f:
                content = f.read()

            self.send_response(200)
            self.send_header('Content-type', 'application/xml')
            self.end_headers()
            self.wfile.write(content.encode())
        except FileNotFoundError:
            # Generate default sitemap.xml if file doesn't exist
            from datetime import datetime
            today = datetime.now().strftime('%Y-%m-%d')
            content = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://wa-creel.jeremyveleber.com/</loc>
    <lastmod>{today}</lastmod>
    <changefreq>weekly</changefreq>
    <priority>1.0</priority>
  </url>
</urlset>"""
            self.send_response(200)
            self.send_header('Content-type', 'application/xml')
            self.end_headers()
            self.wfile.write(content.encode())
        except Exception as e:
            print(f"Error serving sitemap.xml: {e}")
            self.send_error(500, f"Server error: {str(e)}")

    def serve_statistics(self, params):
        """Serve overall statistics"""
        try:
            stats = database.get_statistics(params)
            self.send_json(stats)
        except Exception as e:
            print(f"Error serving statistics: {e}")
            import traceback
            traceback.print_exc()
            self.send_error(500, f"Server error: {str(e)}")

    def serve_areas(self, params):
        """Serve list of catch areas with totals"""
        try:
            areas = database.get_catch_areas(params)
            # Convert to list of dicts
            areas_list = [{'area': area, 'total': total} for area, total in areas]
            self.send_json(areas_list)
        except Exception as e:
            print(f"Error serving areas: {e}")
            import traceback
            traceback.print_exc()
            self.send_error(500, f"Server error: {str(e)}")

    def serve_filter_options(self):
        """Get available filter options (years and catch areas)"""
        try:
            conn = database.get_db_connection()
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
        except Exception as e:
            print(f"Error serving filter options: {e}")
            import traceback
            traceback.print_exc()
            self.send_error(500, f"Server error: {str(e)}")

    def serve_yearly_data(self, params):
        """Yearly catch trends"""
        try:
            conn = database.get_db_connection()
            cursor = conn.cursor()

            where_clause, query_params = database.build_where_clause(params)

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
        except Exception as e:
            print(f"Error serving yearly data: {e}")
            import traceback
            traceback.print_exc()
            self.send_error(500, f"Server error: {str(e)}")

    def serve_trend_data(self, params):
        """Trend data with configurable time granularity"""
        try:
            conn = database.get_db_connection()
            cursor = conn.cursor()

            time_unit = params.get('time_unit', ['yearly'])[0]
            where_clause, query_params = database.build_where_clause(params)

            # Get list of species to display
            species_list = database.get_species_list(params)

            # Build species SELECT columns
            species_select = ', '.join([f"SUM({s}) as {s}" for s in species_list])

            # sample_date format: "Apr 1, 2013" (Mon DD, YYYY)
            # We need to convert month names to numbers
            month_case = """
                CASE substr(sample_date, 1, 3)
                    WHEN 'Jan' THEN '01'
                    WHEN 'Feb' THEN '02'
                    WHEN 'Mar' THEN '03'
                    WHEN 'Apr' THEN '04'
                    WHEN 'May' THEN '05'
                    WHEN 'Jun' THEN '06'
                    WHEN 'Jul' THEN '07'
                    WHEN 'Aug' THEN '08'
                    WHEN 'Sep' THEN '09'
                    WHEN 'Oct' THEN '10'
                    WHEN 'Nov' THEN '11'
                    WHEN 'Dec' THEN '12'
                END
            """

            # Extract day (between first space and comma)
            day_extract = "substr('0' || substr(sample_date, 5, instr(sample_date, ',') - 5), -2, 2)"

            # Extract year (last 4 characters)
            year_extract = "substr(sample_date, -4)"

            # Build YYYY-MM-DD date string
            date_string = f"{year_extract} || '-' || {month_case} || '-' || {day_extract}"

            # Determine time period extraction based on granularity
            if time_unit == 'daily':
                period_select = f"{date_string} as period"
            elif time_unit == 'weekly':
                # Format: YYYY-Www (e.g., 2024-W01)
                period_select = f"strftime('%Y-W%W', {date_string}) as period"
            elif time_unit == 'monthly':
                # Format: YYYY-MM (e.g., 2024-01)
                period_select = f"{year_extract} || '-' || {month_case} as period"
            else:  # yearly (default)
                period_select = f"{year_extract} as period"

            query = f"""
                SELECT 
                    {period_select},
                    {species_select}
                FROM creel_records
                {where_clause}
                {"AND" if where_clause else "WHERE"} length(sample_date) > 0
                GROUP BY period
                ORDER BY period
            """

            cursor.execute(query, query_params)
            columns = ['period'] + species_list
            rows = cursor.fetchall()
            conn.close()

            # Convert to list of dicts
            data = [dict(zip(columns, row)) for row in rows]
            self.send_json(data)

        except Exception as e:
            print(f"Error serving trend data: {e}")
            import traceback
            traceback.print_exc()
            self.send_error(500, f"Server error: {str(e)}")

    def serve_species_totals(self, params):
        """Species breakdown totals"""
        try:
            conn = database.get_db_connection()
            cursor = conn.cursor()

            where_clause, query_params = database.build_where_clause(params)
            species_list = database.get_species_list(params)

            # Build query to get totals for each species
            species_select = ', '.join([f"SUM({s}) as {s}" for s in species_list])

            query = f"""
                SELECT {species_select}
                FROM creel_records
                {where_clause}
            """

            cursor.execute(query, query_params)
            row = cursor.fetchone()
            conn.close()

            # Convert to dict
            data = {species: (row[i] or 0) for i, species in enumerate(species_list)}
            self.send_json(data)

        except Exception as e:
            print(f"Error serving species totals: {e}")
            import traceback
            traceback.print_exc()
            self.send_error(500, f"Server error: {str(e)}")

    def serve_monthly_data(self, params):
        """Monthly catch patterns"""
        try:
            conn = database.get_db_connection()
            cursor = conn.cursor()

            where_clause, query_params = database.build_where_clause(params)
            species_columns = database.get_species_columns(params)

            query = f"""
                SELECT 
                    CASE substr(sample_date, 1, 3)
                        WHEN 'Jan' THEN 1 WHEN 'Feb' THEN 2 WHEN 'Mar' THEN 3
                        WHEN 'Apr' THEN 4 WHEN 'May' THEN 5 WHEN 'Jun' THEN 6
                        WHEN 'Jul' THEN 7 WHEN 'Aug' THEN 8 WHEN 'Sep' THEN 9
                        WHEN 'Oct' THEN 10 WHEN 'Nov' THEN 11 WHEN 'Dec' THEN 12
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

            # Fill all 12 months (some may have no data)
            monthly_totals = [0] * 12
            for row in rows:
                month = row[0]
                if month and 1 <= month <= 12:
                    monthly_totals[month - 1] = row[1] or 0

            # Return all 12 months with 'month' and 'total' keys
            data = [{'month': i + 1, 'total': monthly_totals[i]} for i in range(12)]
            self.send_json(data)

        except Exception as e:
            print(f"Error serving monthly data: {e}")
            import traceback
            traceback.print_exc()
            self.send_error(500, f"Server error: {str(e)}")

    def serve_map_data(self, params):
        """Map data with area totals"""
        try:
            conn = database.get_db_connection()
            cursor = conn.cursor()

            where_clause, query_params = database.build_where_clause(params)
            species_columns = database.get_species_columns(params)

            query = f"""
                SELECT 
                    catch_area,
                    SUM({species_columns}) as total,
                    COUNT(*) as surveys
                FROM creel_records
                {where_clause}
                {"AND" if where_clause else "WHERE"} catch_area != ''
                GROUP BY catch_area
            """

            cursor.execute(query, query_params)
            rows = cursor.fetchall()
            conn.close()

            # Convert to array of objects (matching old format)
            data = [{'area': row[0], 'total': row[1] or 0, 'surveys': row[2] or 0} for row in rows]
            self.send_json(data)

        except Exception as e:
            print(f"Error serving map data: {e}")
            import traceback
            traceback.print_exc()
            self.send_error(500, f"Server error: {str(e)}")

    def serve_update_data(self):
        """Update data from WDFW if it's been more than 24 hours"""
        if WDFWCreelCollector is None:
            self.send_json({
                'success': False,
                'message': 'Data collector not available.',
                'last_update': None,
                'should_reload': False
            })
            return

        # Check last update time
        last_update = database.get_last_update_time()
        now = datetime.now()

        if last_update:
            time_since_update = now - last_update
            hours_since_update = time_since_update.total_seconds() / 3600

            # If updated within last 24 hours, don't update again
            if hours_since_update < Config.UPDATE_INTERVAL_HOURS:
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
                # Calculate how many years to fetch from current year back to 2013
                current_year = datetime.now().year
                max_years = current_year - 2013 + 1

                # Fetch data
                collector.fetch_all_data(max_years=max_years)

                # Record update time
                database.set_last_update_time()

                # Get record count
                cursor = collector.conn.cursor()
                cursor.execute('SELECT COUNT(*) FROM creel_records')
                total_records = cursor.fetchone()[0]

                print("=" * 70)
                print(f"✅ Update completed successfully! Total records: {total_records:,}")
                print("=" * 70)

                # Upload database to GCS
                if Config.GCS_BUCKET_NAME:
                    gcs_storage.upload_database_to_gcs(Config.GCS_BUCKET_NAME, Config.DB_PATH)
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

    def send_json(self, data):
        """Send JSON response"""
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def log_message(self, format, *args):
        """Override to customize logging"""
        # Only log errors, not every request
        if '40' in str(args[1]) or '50' in str(args[1]):
            super().log_message(format, *args)


def run_server():
    """Start the HTTP server"""
    # Ensure directories exist
    Config.ensure_directories()

    # Try to download database from GCS
    if Config.GCS_BUCKET_NAME:
        print(f"🪣 GCS Bucket: {Config.GCS_BUCKET_NAME}")
        if not database.database_exists():
            gcs_storage.download_database_from_gcs(Config.GCS_BUCKET_NAME, Config.DB_PATH)
    else:
        print("⚠️  GCS_BUCKET_NAME not set, database will not persist across deployments")

    # Create server
    server = ThreadingHTTPServer((Config.HOST, Config.PORT), CreelDataHandler)

    print("=" * 70)
    print("🎣 WDFW CREEL DASHBOARD SERVER")
    print("=" * 70)

    if database.database_exists():
        print(f"✅ Database found: {os.path.abspath(Config.DB_PATH)}")
    else:
        print(f"⏳ Database will be created on first request")
        print(f"   Location: {os.path.abspath(Config.DB_PATH)}")

    print(f"\n🌐 Server running on port {Config.PORT}")
    print(f"   Local: http://localhost:{Config.PORT}")
    print(f"   Cloud Run: Listening on {Config.HOST}:{Config.PORT}")
    print("\nPress Ctrl+C to stop the server")
    print("=" * 70)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n\n👋 Server stopped")
        server.server_close()