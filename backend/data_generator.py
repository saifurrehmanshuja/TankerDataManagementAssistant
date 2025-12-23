"""
Background Data Generator Service
Generates realistic tanker data every 30 seconds and manages status transitions
"""
import psycopg2
import random
import time
import threading
from datetime import datetime, timedelta
from config import (
    POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_HOST, 
    POSTGRES_PORT, DATABASE_NAME, STATUS_TRANSITION_INTERVAL
)
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TankerDataGenerator:
    """Generates realistic tanker data and manages status transitions"""
    
    def __init__(self):
        self.running = False
        self.thread = None
        self.status_transition_thread = None
        
        # Realistic data pools
        self.driver_names = [
            "Ahmed Khan", "Mohammad Ali", "Fatima Noor", "Bilal Hassan",
            "Sara Ahmed", "Hassan Malik", "Ayesha Khan", "Usman Ali",
            "Zainab Sheikh", "Omar Farooq", "Nida Hussain", "Tariq Mehmood"
        ]
        
        self.depots = [
            ("Islamabad", 33.6844, 73.0479),
            ("Lahore", 31.5204, 74.3587),
            ("Karachi", 24.8607, 67.0011),
            ("Rawalpindi", 33.5651, 73.0169),
            ("Faisalabad", 31.4504, 73.1350),
            ("Multan", 30.1575, 71.5249)
        ]
        
        self.destinations = [
            ("Customer X", 33.6844, 73.0479),
            ("Customer Y", 31.5204, 74.3587),
            ("Customer Z", 24.8607, 67.0011),
            ("Customer A", 33.5651, 73.0169),
            ("Customer B", 31.4504, 73.1350),
            ("Customer C", 30.1575, 71.5249)
        ]
        
        self.statuses = ["At Source", "In Transit", "Reached Destination", "Delayed", "Loading", "Unloading"]
        
        # Status transition rules (deterministic)
        self.status_transitions = {
            "At Source": {"next": "Loading", "duration_minutes": 15},
            "Loading": {"next": "In Transit", "duration_minutes": 30},
            "In Transit": {"next": "Reached Destination", "duration_minutes": 300},  # 5 hours
            "Reached Destination": {"next": "Unloading", "duration_minutes": 45},
            "Unloading": {"next": "At Source", "duration_minutes": 60},
            "Delayed": {"next": "In Transit", "duration_minutes": 60},  # After delay, continue transit
            "Reached Destination": {"next": "Unloading", "duration_minutes": 45}
        }
    
    def get_db_connection(self):
        """Create and return a database connection"""
        try:
            conn = psycopg2.connect(
                dbname=DATABASE_NAME,
                user=POSTGRES_USER,
                password=POSTGRES_PASSWORD,
                host=POSTGRES_HOST,
                port=POSTGRES_PORT
            )
            return conn
        except Exception as e:
            logger.error(f"Database connection error: {e}")
            return None
    
    def get_or_create_driver(self, conn, driver_name):
        """Get or create a driver and return driver_id"""
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT driver_id FROM drivers WHERE driver_name = %s", (driver_name,))
            result = cursor.fetchone()
            if result:
                return result[0]
            else:
                cursor.execute("INSERT INTO drivers (driver_name) VALUES (%s) RETURNING driver_id", (driver_name,))
                conn.commit()
                return cursor.fetchone()[0]
        finally:
            cursor.close()
    
    def get_or_create_depot(self, conn, depot_name, lat, lon):
        """Get or create a depot and return depot_id"""
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT depot_id FROM depots WHERE depot_name = %s", (depot_name,))
            result = cursor.fetchone()
            if result:
                return result[0]
            else:
                cursor.execute(
                    "INSERT INTO depots (depot_name, location_lat, location_lon) VALUES (%s, %s, %s) RETURNING depot_id",
                    (depot_name, lat, lon)
                )
                conn.commit()
                return cursor.fetchone()[0]
        finally:
            cursor.close()
    
    def get_or_create_destination(self, conn, dest_name, lat, lon):
        """Get or create a destination and return destination_id"""
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT destination_id FROM destinations WHERE destination_name = %s", (dest_name,))
            result = cursor.fetchone()
            if result:
                return result[0]
            else:
                cursor.execute(
                    "INSERT INTO destinations (destination_name, location_lat, location_lon) VALUES (%s, %s, %s) RETURNING destination_id",
                    (dest_name, lat, lon)
                )
                conn.commit()
                return cursor.fetchone()[0]
        finally:
            cursor.close()
    
    def generate_realistic_tanker(self, tanker_id=None):
        """Generate a realistic tanker record"""
        if tanker_id is None:
            # Generate new tanker ID
            existing_ids = self.get_existing_tanker_ids()
            max_num = max([int(id.split('-')[1]) for id in existing_ids if '-' in id and id.split('-')[1].isdigit()], default=0)
            tanker_id = f"TNK-{max_num + 1:03d}"
        
        # Select realistic combinations
        depot = random.choice(self.depots)
        destination = random.choice(self.destinations)
        driver_name = random.choice(self.driver_names)
        
        # Determine status based on realistic scenarios
        status = random.choice(["At Source", "In Transit", "Loading"])
        
        # Generate realistic oil volume (80-95% of capacity for in-transit, 0-20% for at source)
        max_capacity = random.choice([18000, 20000, 22000, 25000])
        if status == "At Source":
            oil_volume = random.uniform(0, max_capacity * 0.2)
        elif status == "Loading":
            oil_volume = random.uniform(max_capacity * 0.5, max_capacity * 0.8)
        else:  # In Transit
            oil_volume = random.uniform(max_capacity * 0.8, max_capacity * 0.95)
        
        # Generate location based on status
        if status == "At Source":
            lat, lon = depot[1], depot[2]
        elif status == "In Transit":
            # Interpolate between depot and destination
            progress = random.uniform(0.2, 0.8)
            lat = depot[1] + (destination[1] - depot[1]) * progress
            lon = depot[2] + (destination[2] - depot[2]) * progress
        else:
            lat, lon = depot[1], depot[2]
        
        # Generate realistic trip metrics
        trip_duration = random.uniform(1.0, 6.0) if status == "In Transit" else 0
        avg_speed = random.uniform(60, 80) if status == "In Transit" else 0
        
        # Seal status (realistic: sealed when in transit, open when at source/loading)
        seal_status = "Sealed" if status in ["In Transit", "Reached Destination"] else "Open"
        
        return {
            "tanker_id": tanker_id,
            "driver_name": driver_name,
            "current_status": status,
            "current_location_lat": round(lat, 6),
            "current_location_lon": round(lon, 6),
            "source_depot": depot[0],
            "depot_lat": depot[1],
            "depot_lon": depot[2],
            "destination": destination[0],
            "dest_lat": destination[1],
            "dest_lon": destination[2],
            "seal_status": seal_status,
            "oil_volume_liters": round(oil_volume, 2),
            "max_capacity_liters": max_capacity,
            "trip_duration_hours": round(trip_duration, 2),
            "avg_speed_kmh": round(avg_speed, 2)
        }
    
    def get_existing_tanker_ids(self):
        """Get list of existing tanker IDs"""
        conn = self.get_db_connection()
        if not conn:
            return []
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT tanker_id FROM tankers")
            ids = [row[0] for row in cursor.fetchall()]
            cursor.close()
            return ids
        except Exception as e:
            logger.error(f"Error fetching tanker IDs: {e}")
            return []
        finally:
            conn.close()
    
    def insert_or_update_tanker(self, tanker_data):
        """Insert or update tanker in database"""
        conn = self.get_db_connection()
        if not conn:
            return False
        
        try:
            cursor = conn.cursor()
            
            # Get or create related entities
            driver_id = self.get_or_create_driver(conn, tanker_data["driver_name"])
            depot_id = self.get_or_create_depot(
                conn, tanker_data["source_depot"], 
                tanker_data["depot_lat"], tanker_data["depot_lon"]
            )
            dest_id = self.get_or_create_destination(
                conn, tanker_data["destination"],
                tanker_data["dest_lat"], tanker_data["dest_lon"]
            )
            
            # Check if tanker exists
            cursor.execute("SELECT current_status, status_changed_at FROM tankers WHERE LOWER(tanker_id) = LOWER(%s)", 
                          (tanker_data["tanker_id"],))
            existing = cursor.fetchone()
            
            current_time = datetime.now()
            
            if existing:
                # Update existing tanker
                old_status, status_changed_at = existing
                new_status = tanker_data["current_status"]
                
                # Only update status_changed_at if status actually changed
                status_changed_at_sql = "status_changed_at"
                if old_status != new_status:
                    status_changed_at_sql = "CURRENT_TIMESTAMP"
                
                cursor.execute(f"""
                    UPDATE tankers SET
                        driver_id = %s,
                        current_status = %s,
                        current_location_lat = %s,
                        current_location_lon = %s,
                        source_depot_id = %s,
                        destination_id = %s,
                        seal_status = %s,
                        oil_volume_liters = %s,
                        max_capacity_liters = %s,
                        last_update = CURRENT_TIMESTAMP,
                        trip_duration_hours = %s,
                        avg_speed_kmh = %s,
                        status_changed_at = {status_changed_at_sql},
                        updated_at = CURRENT_TIMESTAMP
                    WHERE LOWER(tanker_id) = LOWER(%s)
                """, (
                    driver_id, new_status,
                    tanker_data["current_location_lat"],
                    tanker_data["current_location_lon"],
                    depot_id, dest_id,
                    tanker_data["seal_status"],
                    tanker_data["oil_volume_liters"],
                    tanker_data["max_capacity_liters"],
                    tanker_data["trip_duration_hours"],
                    tanker_data["avg_speed_kmh"],
                    tanker_data["tanker_id"]
                ))
            else:
                # Insert new tanker
                cursor.execute("""
                    INSERT INTO tankers (
                        tanker_id, driver_id, current_status,
                        current_location_lat, current_location_lon,
                        source_depot_id, destination_id,
                        seal_status, oil_volume_liters, max_capacity_liters,
                        last_update, trip_duration_hours, avg_speed_kmh,
                        status_changed_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, %s, %s, CURRENT_TIMESTAMP)
                """, (
                    tanker_data["tanker_id"], driver_id, tanker_data["current_status"],
                    tanker_data["current_location_lat"], tanker_data["current_location_lon"],
                    depot_id, dest_id,
                    tanker_data["seal_status"], tanker_data["oil_volume_liters"],
                    tanker_data["max_capacity_liters"],
                    tanker_data["trip_duration_hours"], tanker_data["avg_speed_kmh"]
                ))
            
            # Insert into history table
            cursor.execute("""
                INSERT INTO tanker_history (
                    tanker_id, driver_id, status,
                    location_lat, location_lon,
                    source_depot_id, destination_id,
                    seal_status, oil_volume_liters, max_capacity_liters,
                    trip_duration_hours, avg_speed_kmh,
                    recorded_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
            """, (
                tanker_data["tanker_id"], driver_id, tanker_data["current_status"],
                tanker_data["current_location_lat"], tanker_data["current_location_lon"],
                depot_id, dest_id,
                tanker_data["seal_status"], tanker_data["oil_volume_liters"],
                tanker_data["max_capacity_liters"],
                tanker_data["trip_duration_hours"], tanker_data["avg_speed_kmh"]
            ))
            
            conn.commit()
            cursor.close()
            return True
            
        except Exception as e:
            logger.error(f"Error inserting/updating tanker: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()
    
    def process_status_transitions(self):
        """Process automatic status transitions based on time elapsed"""
        conn = self.get_db_connection()
        if not conn:
            return
        
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT tanker_id, current_status, status_changed_at
                FROM tankers
                WHERE current_status IN ('At Source', 'Loading', 'In Transit', 'Reached Destination', 'Unloading', 'Delayed')
            """)
            
            tankers = cursor.fetchall()
            current_time = datetime.now()
            updates = []
            
            for tanker_id, status, status_changed_at in tankers:
                if status_changed_at:
                    elapsed_minutes = (current_time - status_changed_at).total_seconds() / 60
                    
                    if status in self.status_transitions:
                        transition = self.status_transitions[status]
                        if elapsed_minutes >= transition["duration_minutes"]:
                            new_status = transition["next"]
                            updates.append((tanker_id, new_status))
            
            # Apply updates
            for tanker_id, new_status in updates:
                # Get current tanker data to update location appropriately
                cursor.execute("""
                    SELECT t.*, d.location_lat as dest_lat, d.location_lon as dest_lon,
                           dep.location_lat as depot_lat, dep.location_lon as depot_lon
                    FROM tankers t
                    LEFT JOIN destinations d ON t.destination_id = d.destination_id
                    LEFT JOIN depots dep ON t.source_depot_id = dep.depot_id
                    WHERE LOWER(t.tanker_id) = LOWER(%s)
                """, (tanker_id,))
                
                tanker = cursor.fetchone()
                if tanker:
                    cols = [desc[0] for desc in cursor.description]
                    tanker_dict = dict(zip(cols, tanker))
                    
                    # Update location based on new status
                    if new_status == "Reached Destination":
                        new_lat = tanker_dict.get("dest_lat") or tanker_dict.get("current_location_lat")
                        new_lon = tanker_dict.get("dest_lon") or tanker_dict.get("current_location_lon")
                    elif new_status == "At Source":
                        new_lat = tanker_dict.get("depot_lat") or tanker_dict.get("current_location_lat")
                        new_lon = tanker_dict.get("depot_lon") or tanker_dict.get("current_location_lon")
                    else:
                        new_lat = tanker_dict.get("current_location_lat")
                        new_lon = tanker_dict.get("current_location_lon")
                    
                    # Update seal status
                    new_seal = "Sealed" if new_status in ["In Transit", "Reached Destination"] else "Open"
                    
                    cursor.execute("""
                        UPDATE tankers SET
                            current_status = %s,
                            current_location_lat = %s,
                            current_location_lon = %s,
                            seal_status = %s,
                            status_changed_at = CURRENT_TIMESTAMP,
                            last_update = CURRENT_TIMESTAMP,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE LOWER(tanker_id) = LOWER(%s)
                    """, (new_status, new_lat, new_lon, new_seal, tanker_id))
                    
                    # Add to history
                    cursor.execute("""
                        INSERT INTO tanker_history (
                            tanker_id, driver_id, status,
                            location_lat, location_lon,
                            source_depot_id, destination_id,
                            seal_status, oil_volume_liters, max_capacity_liters,
                            trip_duration_hours, avg_speed_kmh
                        )
                        SELECT 
                            tanker_id, driver_id, %s,
                            %s, %s,
                            source_depot_id, destination_id,
                            %s, oil_volume_liters, max_capacity_liters,
                            trip_duration_hours, avg_speed_kmh
                        FROM tankers
                        WHERE LOWER(tanker_id) = LOWER(%s)
                    """, (new_status, new_lat, new_lon, new_seal, tanker_id))
                    
                    logger.info(f"Status transition: {tanker_id} {status} -> {new_status}")
            
            conn.commit()
            cursor.close()
            
        except Exception as e:
            logger.error(f"Error processing status transitions: {e}")
            conn.rollback()
        finally:
            conn.close()
    
    def generate_data_cycle(self):
        """Single cycle of data generation"""
        try:
            # Generate 1-3 new or update existing tankers
            num_operations = random.randint(1, 3)
            existing_ids = self.get_existing_tanker_ids()
            
            for _ in range(num_operations):
                # 70% chance to update existing, 30% to create new
                if existing_ids and random.random() < 0.7:
                    tanker_id = random.choice(existing_ids)
                    tanker_data = self.generate_realistic_tanker(tanker_id)
                else:
                    tanker_data = self.generate_realistic_tanker()
                
                self.insert_or_update_tanker(tanker_data)
                logger.info(f"Generated/Updated tanker: {tanker_data['tanker_id']}")
            
        except Exception as e:
            logger.error(f"Error in data generation cycle: {e}")
    
    def status_transition_worker(self):
        """Background worker for status transitions"""
        while self.running:
            try:
                self.process_status_transitions()
                time.sleep(STATUS_TRANSITION_INTERVAL)
            except Exception as e:
                logger.error(f"Error in status transition worker: {e}")
                time.sleep(60)  # Wait a minute before retrying
    
    def data_generation_worker(self):
        """Background worker for data generation"""
        from config import DATA_GENERATION_INTERVAL
        
        while self.running:
            try:
                self.generate_data_cycle()
                time.sleep(DATA_GENERATION_INTERVAL)
            except Exception as e:
                logger.error(f"Error in data generation worker: {e}")
                time.sleep(60)  # Wait a minute before retrying
    
    def start(self):
        """Start the background services"""
        if self.running:
            logger.warning("Data generator is already running")
            return
        
        self.running = True
        self.thread = threading.Thread(target=self.data_generation_worker, daemon=True)
        self.status_transition_thread = threading.Thread(target=self.status_transition_worker, daemon=True)
        
        self.thread.start()
        self.status_transition_thread.start()
        logger.info("Data generator started")
    
    def stop(self):
        """Stop the background services"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        if self.status_transition_thread:
            self.status_transition_thread.join(timeout=5)
        logger.info("Data generator stopped")


# Global instance
_generator = None

def get_generator():
    """Get or create the global generator instance"""
    global _generator
    if _generator is None:
        _generator = TankerDataGenerator()
    return _generator

