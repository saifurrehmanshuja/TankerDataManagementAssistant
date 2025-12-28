"""
Ping service for Render keep-alive and uptime monitoring
Pings the health endpoint periodically to keep the service alive
Can be run as a separate worker service on Render or external monitoring service
"""
import os
import time
import requests
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Default Render deployment URL (can be overridden via APP_URL environment variable)
DEFAULT_APP_URL = "https://tankerdatamanagementassistant.onrender.com"

def ping_health_endpoint():
    """Ping the health endpoint"""
    # Get URL from environment variable or use default
    app_url = os.getenv("APP_URL", DEFAULT_APP_URL)
    
    # Remove trailing slash if present
    app_url = app_url.rstrip('/')
    health_url = f"{app_url}/health"
    
    try:
        # Use timeout to prevent hanging
        response = requests.get(health_url, timeout=10)
        
        if response.status_code == 200:
            try:
                data = response.json()
                status = data.get('status', 'unknown')
                timestamp = data.get('timestamp', 'N/A')
                logger.info(f"✅ Health check successful: status={status}, timestamp={timestamp}")
                return True
            except ValueError:
                logger.warning(f"Health check returned non-JSON response: {response.text[:100]}")
                return False
        else:
            logger.warning(f"❌ Health check returned status {response.status_code}")
            return False
            
    except requests.exceptions.Timeout:
        logger.error(f"⏱️ Timeout pinging health endpoint: {health_url}")
        return False
    except requests.exceptions.ConnectionError as e:
        logger.error(f"🔌 Connection error pinging health endpoint: {e}")
        return False
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Error pinging health endpoint: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ Unexpected error pinging health endpoint: {e}")
        return False

def main():
    """Main loop - ping at configurable interval"""
    # Default to 5 minutes (300 seconds), can be overridden via PING_INTERVAL
    ping_interval = int(os.getenv("PING_INTERVAL", "300"))
    
    # Get the URL being used
    app_url = os.getenv("APP_URL", DEFAULT_APP_URL)
    health_url = f"{app_url.rstrip('/')}/health"
    
    logger.info("=" * 60)
    logger.info("🚀 Starting ping service for uptime monitoring")
    logger.info(f"📍 Target URL: {health_url}")
    logger.info(f"⏰ Ping interval: {ping_interval} seconds ({ping_interval // 60} minutes)")
    logger.info("=" * 60)
    
    consecutive_failures = 0
    max_failures_before_warning = 3
    
    while True:
        try:
            success = ping_health_endpoint()
            
            if success:
                consecutive_failures = 0
            else:
                consecutive_failures += 1
                if consecutive_failures >= max_failures_before_warning:
                    logger.warning(f"⚠️ {consecutive_failures} consecutive failures. Service may be down.")
            
            # Sleep before next ping (non-blocking, uses time.sleep)
            time.sleep(ping_interval)
            
        except KeyboardInterrupt:
            logger.info("🛑 Ping service stopped by user")
            break
        except Exception as e:
            logger.error(f"❌ Unexpected error in ping service: {e}")
            # Continue running even after errors
            time.sleep(ping_interval)

if __name__ == "__main__":
    main()

