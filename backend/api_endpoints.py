"""
REST API Endpoints for Tanker Management System
"""
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timedelta, date
from decimal import Decimal
from config import (
    POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_HOST,
    POSTGRES_PORT, DATABASE_NAME
)
from ml_pipeline import get_ml_pipeline
from city_mapper import get_city_from_coords
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI router
router = APIRouter()


def make_json_serializable(obj):
    """Convert non-JSON-serializable objects to serializable types"""
    if isinstance(obj, Decimal):
        return float(obj)
    elif isinstance(obj, (datetime, date)):
        return obj.isoformat()
    elif isinstance(obj, dict):
        return {key: make_json_serializable(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [make_json_serializable(item) for item in obj]
    elif isinstance(obj, tuple):
        return tuple(make_json_serializable(item) for item in obj)
    return obj


def get_db_connection():
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


@router.get('/tankers')
async def get_all_tankers(
    status: str = Query(None, description="Filter by status"),
    depot: str = Query(None, description="Filter by depot"),
    limit: int = Query(100, ge=1, le=1000, description="Limit results"),
    offset: int = Query(0, ge=0, description="Offset results")
):
    """Get all tankers with current status"""
    try:
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")
        
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Build query
        query = """
            SELECT 
                t.tanker_id,
                dr.driver_name,
                t.current_status,
                t.current_location_lat,
                t.current_location_lon,
                d.depot_name as source_depot,
                dest.destination_name as destination,
                t.seal_status,
                t.oil_volume_liters,
                t.max_capacity_liters,
                t.last_update,
                t.trip_duration_hours,
                t.avg_speed_kmh,
                t.status_changed_at
            FROM tankers t
            LEFT JOIN drivers dr ON t.driver_id = dr.driver_id
            LEFT JOIN depots d ON t.source_depot_id = d.depot_id
            LEFT JOIN destinations dest ON t.destination_id = dest.destination_id
            WHERE 1=1
        """
        
        params = []
        if status:
            query += " AND t.current_status = %s"
            params.append(status)
        
        if depot:
            query += " AND d.depot_name = %s"
            params.append(depot)
        
        query += " ORDER BY t.last_update DESC LIMIT %s OFFSET %s"
        params.extend([limit, offset])
        
        cursor.execute(query, params)
        tankers = cursor.fetchall()
        
        # Add city names to each tanker
        tankers_list = []
        for tanker in tankers:
            tanker_dict = dict(tanker)
            # Add current city name
            if tanker_dict.get('current_location_lat') and tanker_dict.get('current_location_lon'):
                tanker_dict['current_city'] = get_city_from_coords(
                    float(tanker_dict['current_location_lat']),
                    float(tanker_dict['current_location_lon'])
                )
            else:
                tanker_dict['current_city'] = "Unknown Location"
            tankers_list.append(tanker_dict)
        
        cursor.close()
        conn.close()
        
        return {
            'success': True,
            'count': len(tankers_list),
            'tankers': [make_json_serializable(t) for t in tankers_list]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching tankers: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get('/tankers/{tanker_id}')
async def get_tanker_by_id(tanker_id: str):
    """Get a specific tanker by ID"""
    try:
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")
        
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        query = """
            SELECT 
                t.tanker_id,
                dr.driver_name,
                t.current_status,
                t.current_location_lat,
                t.current_location_lon,
                d.depot_name as source_depot,
                dest.destination_name as destination,
                t.seal_status,
                t.oil_volume_liters,
                t.max_capacity_liters,
                t.last_update,
                t.trip_duration_hours,
                t.avg_speed_kmh,
                t.status_changed_at,
                t.created_at
            FROM tankers t
            LEFT JOIN drivers dr ON t.driver_id = dr.driver_id
            LEFT JOIN depots d ON t.source_depot_id = d.depot_id
            LEFT JOIN destinations dest ON t.destination_id = dest.destination_id
            WHERE LOWER(t.tanker_id) = LOWER(%s)
        """
        
        cursor.execute(query, (tanker_id,))
        tanker = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        if tanker:
            # Convert to dict and add city name
            tanker_dict = dict(tanker)
            if tanker_dict.get('current_location_lat') and tanker_dict.get('current_location_lon'):
                tanker_dict['current_city'] = get_city_from_coords(
                    float(tanker_dict['current_location_lat']),
                    float(tanker_dict['current_location_lon'])
                )
            else:
                tanker_dict['current_city'] = "Unknown Location"
            
            # Convert to JSON-serializable format
            serializable_tanker = make_json_serializable(tanker_dict)
            return {
                'success': True,
                'tanker': serializable_tanker
            }
        else:
            raise HTTPException(status_code=404, detail=f'Tanker {tanker_id} not found')
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching tanker: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get('/tankers/{tanker_id}/status')
async def get_tanker_status(tanker_id: str):
    """Get current status of a specific tanker"""
    try:
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")
        
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        query = """
            SELECT 
                t.tanker_id,
                t.current_status,
                t.status_changed_at,
                t.last_update
            FROM tankers t
            WHERE LOWER(t.tanker_id) = LOWER(%s)
        """
        
        cursor.execute(query, (tanker_id,))
        tanker = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        if tanker:
            # Convert to JSON-serializable format
            serializable_status = make_json_serializable(dict(tanker))
            return {
                'success': True,
                'status': serializable_status
            }
        else:
            raise HTTPException(status_code=404, detail=f'Tanker {tanker_id} not found')
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching tanker status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get('/tankers/{tanker_id}/history')
async def get_tanker_history(
    tanker_id: str,
    days: int = Query(30, ge=1, le=365, description="Number of days"),
    limit: int = Query(100, ge=1, le=1000, description="Limit results")
):
    """Get historical records for a specific tanker"""
    try:
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")
        
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        query = """
            SELECT 
                h.tanker_id,
                dr.driver_name,
                h.status,
                h.location_lat,
                h.location_lon,
                d.depot_name as source_depot,
                dest.destination_name as destination,
                h.seal_status,
                h.oil_volume_liters,
                h.max_capacity_liters,
                h.trip_duration_hours,
                h.avg_speed_kmh,
                h.recorded_at
            FROM tanker_history h
            LEFT JOIN drivers dr ON h.driver_id = dr.driver_id
            LEFT JOIN depots d ON h.source_depot_id = d.depot_id
            LEFT JOIN destinations dest ON h.destination_id = dest.destination_id
            WHERE LOWER(h.tanker_id) = LOWER(%s)
                AND h.recorded_at >= CURRENT_TIMESTAMP - INTERVAL '%s days'
            ORDER BY h.recorded_at DESC
            LIMIT %s
        """
        
        cursor.execute(query, (tanker_id, days, limit))
        history = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        # Convert to JSON-serializable format
        serializable_history = [make_json_serializable(dict(h)) for h in history]
        
        return {
            'success': True,
            'count': len(serializable_history),
            'history': serializable_history
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching tanker history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get('/tankers/{tanker_id}/predictions')
async def get_tanker_predictions(tanker_id: str):
    """Get ML predictions for a specific tanker"""
    try:
        ml_pipeline = get_ml_pipeline()
        
        predictions = {
            'tanker_id': tanker_id,
            'arrival_time_hours': None,
            'delay_probability': None,
            'predictions': []
        }
        
        # Get arrival time prediction
        arrival_time = ml_pipeline.predict_arrival_time(tanker_id)
        if arrival_time is not None:
            predictions['arrival_time_hours'] = round(arrival_time, 2)
        
        # Get delay probability
        delay_prob = ml_pipeline.predict_delay_probability(tanker_id)
        if delay_prob is not None:
            predictions['delay_probability'] = round(delay_prob, 4)
        
        # Get stored predictions from database
        conn = get_db_connection()
        if conn:
            try:
                cursor = conn.cursor(cursor_factory=RealDictCursor)
                cursor.execute("""
                    SELECT 
                        p.prediction_type,
                        p.predicted_value,
                        p.confidence_score,
                        p.prediction_data,
                        p.created_at,
                        m.model_version
                    FROM ml_predictions p
                    LEFT JOIN ml_model_metadata m ON p.model_id = m.model_id
                    WHERE LOWER(p.tanker_id) = LOWER(%s)
                    ORDER BY p.created_at DESC
                    LIMIT 10
                """, (tanker_id,))
                
                stored_predictions = cursor.fetchall()
                predictions['predictions'] = [make_json_serializable(dict(p)) for p in stored_predictions]
                
                cursor.close()
            except Exception as e:
                logger.error(f"Error fetching stored predictions: {e}")
            finally:
                conn.close()
        
        return {
            'success': True,
            'predictions': predictions
        }
        
    except Exception as e:
        logger.error(f"Error getting predictions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get('/stats')
async def get_statistics():
    """Get overall statistics about tankers"""
    try:
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")
        
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        query = """
            SELECT 
                COUNT(*) as total_tankers,
                COUNT(DISTINCT t.current_status) as unique_statuses,
                COUNT(DISTINCT d.depot_name) as unique_depots,
                SUM(CASE WHEN t.current_status = 'In Transit' THEN 1 ELSE 0 END) as in_transit,
                SUM(CASE WHEN t.current_status = 'At Source' THEN 1 ELSE 0 END) as at_source,
                SUM(CASE WHEN t.current_status = 'Delayed' THEN 1 ELSE 0 END) as delayed,
                SUM(CASE WHEN t.current_status = 'Reached Destination' THEN 1 ELSE 0 END) as reached_destination,
                AVG(t.oil_volume_liters::numeric) as avg_volume,
                AVG(t.trip_duration_hours::numeric) as avg_duration,
                AVG(t.avg_speed_kmh::numeric) as avg_speed
            FROM tankers t
            LEFT JOIN depots d ON t.source_depot_id = d.depot_id
        """
        
        cursor.execute(query)
        stats = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        # Convert to JSON-serializable format
        serializable_stats = make_json_serializable(dict(stats))
        
        return {
            'success': True,
            'statistics': serializable_stats
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching statistics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get('/health')
async def health():
    """Health check endpoint"""
    return {
        'status': 'healthy',
        'service': 'tanker-management-api',
        'timestamp': datetime.now().isoformat()
    }


@router.get('/analytics/by-city')
async def get_analytics_by_city():
    """Get analytics grouped by city"""
    try:
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")
        
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Get all tankers with their locations
        cursor.execute("""
            SELECT 
                t.tanker_id,
                t.current_status,
                t.current_location_lat,
                t.current_location_lon,
                t.seal_status
            FROM tankers t
        """)
        
        tankers = cursor.fetchall()
        
        # Group by city
        city_stats = {}
        for tanker in tankers:
            tanker_dict = dict(tanker)
            if tanker_dict.get('current_location_lat') and tanker_dict.get('current_location_lon'):
                city = get_city_from_coords(
                    float(tanker_dict['current_location_lat']),
                    float(tanker_dict['current_location_lon'])
                )
            else:
                city = "Unknown Location"
            
            if city not in city_stats:
                city_stats[city] = {
                    'total': 0,
                    'in_transit': 0,
                    'at_source': 0,
                    'delayed': 0,
                    'loading': 0,
                    'unloading': 0,
                    'reached_destination': 0
                }
            
            city_stats[city]['total'] += 1
            status = tanker_dict.get('current_status', '').lower().replace(' ', '_')
            if status in city_stats[city]:
                city_stats[city][status] = city_stats[city].get(status, 0) + 1
        
        cursor.close()
        conn.close()
        
        return {
            'success': True,
            'analytics': make_json_serializable(city_stats)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching city analytics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get('/analytics/delays')
async def get_delay_analytics(
    days: int = Query(7, ge=1, le=365, description="Number of days")
):
    """Get delay analytics"""
    try:
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")
        
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Get delay statistics
        cursor.execute("""
            SELECT 
                COUNT(*) FILTER (WHERE current_status = 'Delayed') as current_delayed,
                COUNT(*) as total_tankers,
                COUNT(*) FILTER (WHERE current_status = 'In Transit') as in_transit,
                AVG(trip_duration_hours::numeric) FILTER (WHERE current_status = 'In Transit') as avg_transit_time
            FROM tankers
        """)
        
        current_stats = dict(cursor.fetchone())
        
        # Get historical delay trends
        cursor.execute("""
            SELECT 
                DATE(recorded_at) as date,
                COUNT(*) FILTER (WHERE status = 'Delayed') as delayed_count,
                COUNT(*) as total_records
            FROM tanker_history
            WHERE recorded_at >= CURRENT_TIMESTAMP - INTERVAL '%s days'
            GROUP BY DATE(recorded_at)
            ORDER BY date DESC
        """, (days,))
        
        trends = [dict(row) for row in cursor.fetchall()]
        
        cursor.close()
        conn.close()
        
        return {
            'success': True,
            'current': make_json_serializable(current_stats),
            'trends': make_json_serializable(trends)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching delay analytics: {e}")
        raise HTTPException(status_code=500, detail=str(e))
