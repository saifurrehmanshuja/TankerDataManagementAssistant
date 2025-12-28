"""
Script to remove placeholder "Customer X", "Customer Y", etc. destinations from the database
"""
import psycopg2
from config import (
    POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_HOST,
    POSTGRES_PORT, DATABASE_NAME
)
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def cleanup_customer_destinations():
    """Remove all destinations with names starting with 'Customer'"""
    try:
        # Connect to the database
        conn = psycopg2.connect(
            dbname=DATABASE_NAME,
            user=POSTGRES_USER,
            password=POSTGRES_PASSWORD,
            host=POSTGRES_HOST,
            port=POSTGRES_PORT
        )
        conn.autocommit = False  # Use transactions
        cursor = conn.cursor()
        
        logger.info("Connected to database. Checking for Customer destinations...")
        
        # First, check what we're about to delete
        cursor.execute("""
            SELECT destination_id, destination_name 
            FROM destinations 
            WHERE destination_name LIKE 'Customer%'
            ORDER BY destination_name
        """)
        customer_destinations = cursor.fetchall()
        
        if not customer_destinations:
            logger.info("✅ No 'Customer' destinations found. Nothing to clean up.")
            cursor.close()
            conn.close()
            return True
        
        logger.info(f"Found {len(customer_destinations)} Customer destinations to remove:")
        for dest_id, dest_name in customer_destinations:
            logger.info(f"  - {dest_name} (ID: {dest_id})")
        
        # Update tankers that reference these destinations
        logger.info("Updating tankers table...")
        cursor.execute("""
            UPDATE tankers 
            SET destination_id = NULL 
            WHERE destination_id IN (
                SELECT destination_id 
                FROM destinations 
                WHERE destination_name LIKE 'Customer%'
            )
        """)
        tankers_updated = cursor.rowcount
        logger.info(f"  Updated {tankers_updated} tanker records")
        
        # Update tanker_history records
        logger.info("Updating tanker_history table...")
        cursor.execute("""
            UPDATE tanker_history 
            SET destination_id = NULL 
            WHERE destination_id IN (
                SELECT destination_id 
                FROM destinations 
                WHERE destination_name LIKE 'Customer%'
            )
        """)
        history_updated = cursor.rowcount
        logger.info(f"  Updated {history_updated} history records")
        
        # Delete the placeholder destinations
        logger.info("Deleting Customer destinations...")
        cursor.execute("""
            DELETE FROM destinations 
            WHERE destination_name LIKE 'Customer%'
        """)
        deleted_count = cursor.rowcount
        logger.info(f"  Deleted {deleted_count} destination records")
        
        # Commit the transaction
        conn.commit()
        logger.info("✅ Successfully removed all Customer destinations from the database!")
        
        # Verify removal
        cursor.execute("""
            SELECT COUNT(*) 
            FROM destinations 
            WHERE destination_name LIKE 'Customer%'
        """)
        remaining = cursor.fetchone()[0]
        
        if remaining == 0:
            logger.info("✅ Verification: No Customer destinations remain in the database.")
        else:
            logger.warning(f"⚠️  Warning: {remaining} Customer destinations still exist!")
        
        cursor.close()
        conn.close()
        return True
        
    except Exception as e:
        logger.error(f"❌ Error cleaning up Customer destinations: {e}")
        if conn:
            conn.rollback()
            conn.close()
        return False

if __name__ == "__main__":
    logger.info("Starting cleanup of Customer destinations...")
    success = cleanup_customer_destinations()
    if success:
        logger.info("Cleanup completed successfully!")
    else:
        logger.error("Cleanup failed!")
        exit(1)

