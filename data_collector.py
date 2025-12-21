#!/usr/bin/env python3
"""
WDFW Puget Sound Creel Data Collector
Automatically fetches all available creel data using CSV exports
Stores data in SQLite for efficient querying and scalability
Uses composite keys + data hashing to detect updates vs duplicates
"""

import requests
import csv
import json
import sqlite3
import os
import hashlib
from io import StringIO
from datetime import datetime


class WDFWCreelCollector:
    """Collect all WDFW creel data from CSV exports and store in SQLite"""

    BASE_URL = "https://wdfw.wa.gov/fishing/reports/creel/puget-annual/export"
    DATA_DIR = "wdfw_creel_data"
    DB_FILE = "creel_data.db"

    def __init__(self):
        self.headers = []
        self._ensure_data_directory()
        self.conn = self._init_database()
        self.conflicts = []  # Track data conflicts

    def _ensure_data_directory(self):
        """Create data directory if it doesn't exist"""
        if not os.path.exists(self.DATA_DIR):
            os.makedirs(self.DATA_DIR)
            print(f"📁 Created data directory: {os.path.abspath(self.DATA_DIR)}")

    def _init_database(self):
        """Initialize SQLite database"""
        db_path = os.path.join(self.DATA_DIR, self.DB_FILE)
        is_new = not os.path.exists(db_path)

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row  # Return rows as dictionaries

        if is_new:
            print(f"🗄️ Created new database: {os.path.abspath(db_path)}")
        else:
            print(f"🗄️ Connected to database: {os.path.abspath(db_path)}")

        # Create table with all expected columns
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS creel_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sample_date TEXT,
                ramp_site TEXT,
                catch_area TEXT,
                interviews INTEGER,
                anglers INTEGER,
                chinook REAL,
                chinook_per_angler REAL,
                coho REAL,
                chum REAL,
                pink REAL,
                sockeye REAL,
                lingcod REAL,
                halibut REAL,
                data_hash TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(sample_date, ramp_site, catch_area, interviews, anglers)
            )
        ''')

        # Create indices for common queries
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_sample_date ON creel_records(sample_date)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_catch_area ON creel_records(catch_area)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_ramp_site ON creel_records(ramp_site)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_data_hash ON creel_records(data_hash)')

        conn.commit()
        return conn

    def _get_record_count(self):
        """Get total number of records in database"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM creel_records')
        return cursor.fetchone()[0]

    def _parse_csv(self, csv_text):
        """Parse CSV text into structured data"""
        try:
            csv_reader = csv.DictReader(StringIO(csv_text))
            data = list(csv_reader)
            return data
        except Exception as e:
            print(f"⚠️ Error parsing CSV: {e}")
            return []

    def _safe_float(self, value):
        """Safely convert to float"""
        try:
            return float(value) if value and value.strip() else None
        except (ValueError, AttributeError):
            return None

    def _safe_int(self, value):
        """Safely convert to int"""
        try:
            return int(value) if value and value.strip() else None
        except (ValueError, AttributeError):
            return None

    def _normalize_catch_area(self, value):
        """Normalize catch area - treat N/A, empty, and null as consistent"""
        if not value or str(value).strip() in ('', 'N/A', 'n/a', 'NA', 'null'):
            return ''  # Use empty string instead of NULL for UNIQUE constraint
        return value.strip()

    def _compute_data_hash(self, record):
        """Hash of the actual catch data to detect changes"""
        # Hash only the data fields that might be corrected
        data_fields = [
            str(self._safe_float(record.get('Chinook', ''))),
            str(self._safe_float(record.get('Chinook (per angler)', ''))),
            str(self._safe_float(record.get('Coho', ''))),
            str(self._safe_float(record.get('Chum', ''))),
            str(self._safe_float(record.get('Pink', ''))),
            str(self._safe_float(record.get('Sockeye', ''))),
            str(self._safe_float(record.get('Lingcod', ''))),
            str(self._safe_float(record.get('Halibut', '')))
        ]
        hash_input = '|'.join(data_fields)
        return hashlib.sha256(hash_input.encode()).hexdigest()[:16]

    def _insert_or_update_record(self, record):
        """Insert new record or update if data changed"""
        cursor = self.conn.cursor()

        data_hash = self._compute_data_hash(record)
        catch_area = self._normalize_catch_area(record.get('Catch area', ''))
        sample_date = record.get('Sample date', '')
        ramp_site = record.get('Ramp/site', '')
        interviews = self._safe_int(record.get('# Interviews (Boat or Shore)', ''))
        anglers = self._safe_int(record.get('Anglers', ''))

        try:
            # Try to insert
            cursor.execute('''
                INSERT INTO creel_records (
                    sample_date, ramp_site, catch_area, interviews, anglers,
                    chinook, chinook_per_angler, coho, chum, pink, sockeye, lingcod, halibut,
                    data_hash
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                sample_date,
                ramp_site,
                catch_area,
                interviews,
                anglers,
                self._safe_float(record.get('Chinook', '')),
                self._safe_float(record.get('Chinook (per angler)', '')),
                self._safe_float(record.get('Coho', '')),
                self._safe_float(record.get('Chum', '')),
                self._safe_float(record.get('Pink', '')),
                self._safe_float(record.get('Sockeye', '')),
                self._safe_float(record.get('Lingcod', '')),
                self._safe_float(record.get('Halibut', '')),
                data_hash
            ))

            return 'inserted' if cursor.rowcount > 0 else 'duplicate'

        except sqlite3.IntegrityError:
            # Record exists - check if data changed
            cursor.execute('''
                SELECT data_hash FROM creel_records
                WHERE sample_date = ? AND ramp_site = ? AND catch_area = ? 
                AND interviews IS ? AND anglers IS ?
            ''', (sample_date, ramp_site, catch_area, interviews, anglers))

            existing = cursor.fetchone()
            if existing and existing[0] != data_hash:
                # Data changed - log conflict and update
                self.conflicts.append({
                    'sample_date': sample_date,
                    'ramp_site': ramp_site,
                    'catch_area': catch_area or 'N/A',
                    'interviews': interviews,
                    'anglers': anglers,
                    'old_hash': existing[0],
                    'new_hash': data_hash
                })

                # Data changed - update it
                cursor.execute('''
                    UPDATE creel_records SET
                        chinook = ?, chinook_per_angler = ?, coho = ?, chum = ?,
                        pink = ?, sockeye = ?, lingcod = ?, halibut = ?,
                        data_hash = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE sample_date = ? AND ramp_site = ? AND catch_area = ?
                    AND interviews IS ? AND anglers IS ?
                ''', (
                    self._safe_float(record.get('Chinook', '')),
                    self._safe_float(record.get('Chinook (per angler)', '')),
                    self._safe_float(record.get('Coho', '')),
                    self._safe_float(record.get('Chum', '')),
                    self._safe_float(record.get('Pink', '')),
                    self._safe_float(record.get('Sockeye', '')),
                    self._safe_float(record.get('Lingcod', '')),
                    self._safe_float(record.get('Halibut', '')),
                    data_hash,
                    sample_date,
                    ramp_site,
                    catch_area,
                    interviews,
                    anglers
                ))
                return 'updated'

            return 'duplicate'

        except sqlite3.Error as e:
            print(f"⚠️ Database error: {e}")
            return 'error'

    def fetch_all_data(self, max_years=5):
        """Fetch all available data by iterating through sample_date values

        Args:
            max_years: Maximum number of years to fetch (default: 5)
        """
        print("=" * 70)
        print("WDFW PUGET SOUND CREEL DATA COLLECTOR (SQLite)")
        print("=" * 70)
        print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Max years to fetch: {max_years}")
        print("=" * 70 + "\n")

        # Check existing data
        existing_count = self._get_record_count()
        if existing_count > 0:
            print(f"📊 Found {existing_count:,} records in database\n")

        new_records_count = 0
        updated_records_count = 0
        duplicate_count = 0
        sample_date = 1

        print("🔄 Fetching data from WDFW...\n")

        while sample_date <= max_years:
            # Calculate year for display
            current_year = 2025
            data_year = current_year - sample_date

            url = f"{self.BASE_URL}?sample_date={sample_date}&ramp=&catch_area=&page&_format=csv"

            print(f"[Sample {sample_date}] Year {data_year}... ", end="", flush=True)

            try:
                response = requests.get(url, timeout=30)

                # Check if we've reached the end
                if response.status_code == 404:
                    print("❌ No data available")
                    break

                response.raise_for_status()

                # Parse CSV
                data = self._parse_csv(response.text)

                if not data:
                    print("❌ No data returned")
                    break

                # Insert or update records
                batch_new = 0
                batch_updated = 0
                batch_duplicates = 0

                for record in data:
                    result = self._insert_or_update_record(record)
                    if result == 'inserted':
                        batch_new += 1
                    elif result == 'updated':
                        batch_updated += 1
                    else:
                        batch_duplicates += 1

                # Commit the batch
                self.conn.commit()

                new_records_count += batch_new
                updated_records_count += batch_updated
                duplicate_count += batch_duplicates

                # Detect API bug: if all records are duplicates, API may be broken
                if len(data) > 100 and batch_duplicates == len(data) and batch_new == 0:
                    print(f"\n⚠️  WARNING: All {len(data)} records were duplicates!")
                    print(f"⚠️  WDFW API appears to be returning duplicate data for older years.")
                    print(f"⚠️  Stopping at sample_date={sample_date} (year {data_year}).")
                    print(f"⚠️  Valid data appears to end at year {data_year + 1}.\n")
                    break

                # Show results
                status_parts = [f"{len(data)} total"]
                if batch_new > 0:
                    status_parts.append(f"{batch_new} new")
                if batch_updated > 0:
                    status_parts.append(f"{batch_updated} updated")
                if batch_duplicates > 0:
                    status_parts.append(f"{batch_duplicates} duplicates")

                print(f"✅ {', '.join(status_parts)}")

                # Store headers from first successful fetch
                if not self.headers and data:
                    self.headers = list(data[0].keys())

                sample_date += 1

            except requests.exceptions.RequestException as e:
                if response.status_code == 404:
                    print("❌ No data available")
                else:
                    print(f"⚠️ Error: {e}")
                break
            except Exception as e:
                print(f"⚠️ Error: {e}")
                break

        # Get final count
        final_count = self._get_record_count()

        # Summary
        print("\n" + "=" * 70)
        print("COLLECTION COMPLETE")
        print("=" * 70)
        print(f"Total records in database: {final_count:,}")
        print(f"New records added: {new_records_count:,}")
        print(f"Records updated: {updated_records_count:,}")
        print(f"Duplicates filtered: {duplicate_count:,}")
        print(f"Years fetched: {sample_date - 1} (limit: {max_years})")

        # Show statistics
        self._show_statistics()

        # Show conflicts if any
        if self.conflicts:
            self._show_conflicts()

        print("=" * 70)
        print(f"Finished at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 70)

        return final_count > 0

    def _show_statistics(self):
        """Show summary statistics from database"""
        cursor = self.conn.cursor()

        print("\n📊 STATISTICS")
        print("-" * 70)

        # Total anglers and interviews
        cursor.execute('SELECT SUM(anglers), SUM(interviews) FROM creel_records')
        total_anglers, total_interviews = cursor.fetchone()

        print(f"Total anglers surveyed: {total_anglers or 0:,}")
        print(f"Total interviews: {total_interviews or 0:,}")

        # Records by year (extract year from date)
        cursor.execute('''
            SELECT substr(sample_date, -4) as year, COUNT(*) as count 
            FROM creel_records 
            WHERE length(sample_date) > 0
            GROUP BY year 
            ORDER BY year DESC
        ''')

        years_data = cursor.fetchall()
        if years_data:
            print("\nRecords by year:")
            for row in years_data:
                if row[0]:  # Has year data
                    print(f"  {row[0]}: {row[1]:,} records")

        # Top catch areas
        cursor.execute('''
            SELECT catch_area, COUNT(*) as count 
            FROM creel_records 
            WHERE catch_area != ''
            GROUP BY catch_area 
            ORDER BY count DESC 
            LIMIT 5
        ''')

        top_areas = cursor.fetchall()
        if top_areas:
            print("\nTop catch areas:")
            for row in top_areas:
                print(f"  {row[0]}: {row[1]:,} records")

        # Check for updated records
        cursor.execute('''
            SELECT COUNT(*) FROM creel_records 
            WHERE updated_at > created_at
        ''')
        updated_count = cursor.fetchone()[0]
        if updated_count > 0:
            print(f"\nRecords with updates: {updated_count:,}")

    def _show_conflicts(self):
        """Show data conflicts detected during collection"""
        print(f"\n⚠️  DATA CONFLICTS DETECTED: {len(self.conflicts)}")
        print("-" * 70)
        print("Multiple records found with same key but different catch data.")
        print("Using 'last one wins' strategy. Review these carefully:\n")

        # Show first 10 conflicts
        for i, conflict in enumerate(self.conflicts[:10], 1):
            print(f"{i}. {conflict['sample_date']} | {conflict['ramp_site']} | "
                  f"{conflict['catch_area']} | Interviews: {conflict['interviews']} | "
                  f"Anglers: {conflict['anglers']}")

        if len(self.conflicts) > 10:
            print(f"\n... and {len(self.conflicts) - 10} more conflicts")

        print("\nNote: This may indicate data quality issues in source CSV files.")

    def export_to_json(self, filename=None):
        """Export database to JSON file"""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"creel_export_{timestamp}.json"

        filepath = os.path.join(self.DATA_DIR, filename)

        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM creel_records')

        # Convert to list of dicts
        records = []
        for row in cursor.fetchall():
            record = dict(row)
            # Remove internal fields
            record.pop('id', None)
            record.pop('data_hash', None)
            record.pop('created_at', None)
            record.pop('updated_at', None)
            records.append(record)

        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(records, f, indent=2)
            print(f"\n💾 Exported {len(records):,} records to: {os.path.abspath(filepath)}")
            return True
        except Exception as e:
            print(f"⚠️ Error exporting: {e}")
            return False

    def inspect_csv(self, sample_date):
        """Fetch and inspect a specific CSV for duplicates"""
        url = f"{self.BASE_URL}?sample_date={sample_date}&ramp=&catch_area=&page&_format=csv"

        print(f"\n🔍 INSPECTING CSV for sample_date={sample_date}")
        print(f"URL: {url}")
        print("=" * 70)

        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()

            data = self._parse_csv(response.text)
            print(f"Total rows in CSV: {len(data)}\n")

            # Check for duplicates by creating composite keys
            seen_keys = {}
            duplicates = []

            for i, record in enumerate(data):
                key = (
                    record.get('Sample date', ''),
                    record.get('Ramp/site', ''),
                    self._normalize_catch_area(record.get('Catch area', '')),
                    self._safe_int(record.get('# Interviews (Boat or Shore)', '')),
                    self._safe_int(record.get('Anglers', ''))
                )

                data_hash = self._compute_data_hash(record)

                if key in seen_keys:
                    duplicates.append({
                        'row': i + 1,
                        'key': key,
                        'first_row': seen_keys[key]['row'],
                        'first_hash': seen_keys[key]['hash'],
                        'current_hash': data_hash,
                        'same_data': seen_keys[key]['hash'] == data_hash
                    })
                else:
                    seen_keys[key] = {'row': i + 1, 'hash': data_hash}

            if duplicates:
                print(f"⚠️  Found {len(duplicates)} duplicate keys in CSV:\n")

                exact_dupes = [d for d in duplicates if d['same_data']]
                conflict_dupes = [d for d in duplicates if not d['same_data']]

                if exact_dupes:
                    print(f"📋 {len(exact_dupes)} exact duplicates (same key + same data):")
                    for d in exact_dupes[:5]:
                        print(f"  Row {d['row']} duplicates row {d['first_row']}")
                        print(f"    Key: {d['key'][0]} | {d['key'][1]} | {d['key'][2] or 'N/A'}")
                    if len(exact_dupes) > 5:
                        print(f"  ... and {len(exact_dupes) - 5} more")

                if conflict_dupes:
                    print(f"\n⚠️  {len(conflict_dupes)} data conflicts (same key + different data):")
                    for d in conflict_dupes[:5]:
                        print(f"  Row {d['row']} conflicts with row {d['first_row']}")
                        print(f"    Key: {d['key'][0]} | {d['key'][1]} | {d['key'][2] or 'N/A'}")
                    if len(conflict_dupes) > 5:
                        print(f"  ... and {len(conflict_dupes) - 5} more")

                print("\n💡 This suggests WDFW's CSV export has data quality issues.")
            else:
                print("✅ No duplicates found - CSV is clean!")

            return data

        except Exception as e:
            print(f"⚠️ Error: {e}")
            return None

    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()


def main():
    """Main entry point"""
    import sys

    collector = WDFWCreelCollector()

    try:
        # Check if user wants to inspect a specific CSV
        if len(sys.argv) > 1 and sys.argv[1] == 'inspect':
            sample_date = int(sys.argv[2]) if len(sys.argv) > 2 else 10
            collector.inspect_csv(sample_date)
        else:
            # Note: WDFW API returns duplicate current-year data for sample_date > 13
            # Actual data only available from 2012-present (samples 1-13)
            collector.fetch_all_data(max_years=13)
    except KeyboardInterrupt:
        print("\n\n⚠️ Interrupted by user")
    except Exception as e:
        print(f"\n⚠️ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        collector.close()


if __name__ == "__main__":
    main()