"""
Database Initialization Script
Creates all required tables if they don't exist
"""
import psycopg2
from psycopg2 import errors
from pathlib import Path
import logging
from config import (
    POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_HOST,
    POSTGRES_PORT, DATABASE_NAME
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def init_database():
    """Initialize database with schema"""
    try:
        # Connect to the database
        conn = psycopg2.connect(
            dbname=DATABASE_NAME,
            user=POSTGRES_USER,
            password=POSTGRES_PASSWORD,
            host=POSTGRES_HOST,
            port=POSTGRES_PORT
        )
        conn.autocommit = True
        cursor = conn.cursor()
        
        logger.info("Connected to database. Checking if tables exist...")
        
        # Check if tables exist
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name IN ('tankers', 'drivers', 'depots', 'destinations')
        """)
        existing_tables = [row[0] for row in cursor.fetchall()]
        
        if len(existing_tables) >= 4:
            logger.info("✅ Database tables already exist. Skipping initialization.")
            cursor.close()
            conn.close()
            return True
        
        logger.info("Tables not found. Reading schema file...")
        
        # Read and execute schema file
        schema_path = Path(__file__).parent / 'database_schema.sql'
        
        if not schema_path.exists():
            logger.error(f"Schema file not found at {schema_path}")
            return False
        
        with open(schema_path, 'r', encoding='utf-8') as f:
            schema_sql = f.read()
        
        logger.info("Executing schema...")
        
        # Remove DROP statements for safety in production
        import re
        safe_schema = schema_sql
        # Replace DROP statements with comments
        safe_schema = re.sub(r'DROP TABLE IF EXISTS.*?CASCADE;', '-- DROP statement skipped', safe_schema, flags=re.IGNORECASE | re.MULTILINE | re.DOTALL)
        safe_schema = re.sub(r'DROP TABLE.*?CASCADE;', '-- DROP statement skipped', safe_schema, flags=re.IGNORECASE | re.MULTILINE | re.DOTALL)
        
        # Split SQL into individual statements and execute one by one
        # This is necessary because psycopg2 execute() only handles one statement
        statements = []
        current_statement = []
        
        for line in safe_schema.split('\n'):
            line = line.strip()
            # Skip empty lines and comments
            if not line or line.startswith('--'):
                continue
            
            current_statement.append(line)
            # If line ends with semicolon, it's the end of a statement
            if line.endswith(';'):
                statement = ' '.join(current_statement)
                if statement and not statement.startswith('--'):
                    statements.append(statement)
                current_statement = []
        
        # Execute each statement
        executed_count = 0
        for statement in statements:
            if not statement or 'DROP' in statement.upper():
                continue
            try:
                cursor.execute(statement)
                executed_count += 1
            except (errors.DuplicateTable, errors.DuplicateObject) as e:
                logger.debug(f"Already exists (skipping): {str(e)[:50]}")
            except psycopg2.Error as e:
                error_msg = str(e).lower()
                error_code = getattr(e, 'pgcode', None)
                # PostgreSQL error codes for "already exists" scenarios
                # 42P07 = duplicate_table, 42710 = duplicate_object
                if error_code in ('42P07', '42710') or 'already exists' in error_msg or 'duplicate' in error_msg:
                    logger.debug(f"Already exists (skipping): {str(e)[:50]}")
                else:
                    logger.warning(f"Error executing statement: {str(e)[:150]}")
                    logger.debug(f"Statement was: {statement[:100]}...")
            except Exception as e:
                error_msg = str(e).lower()
                # Ignore "already exists" errors
                if 'already exists' not in error_msg and 'duplicate' not in error_msg:
                    logger.warning(f"Unexpected error executing statement: {str(e)[:150]}")
                    logger.debug(f"Statement was: {statement[:100]}...")
        
        logger.info(f"✅ Executed {executed_count} statements successfully")
        
        cursor.close()
        conn.close()
        
        logger.info("✅ Database initialization complete!")
        return True
        
    except psycopg2.OperationalError as e:
        logger.error(f"Database connection error: {e}")
        logger.error("Please check your database credentials and ensure the database exists.")
        return False
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        return False

if __name__ == '__main__':
    logger.info("🚀 Initializing database...")
    success = init_database()
    if success:
        logger.info("✅ Database ready!")
    else:
        logger.error("❌ Database initialization failed!")
        exit(1)

