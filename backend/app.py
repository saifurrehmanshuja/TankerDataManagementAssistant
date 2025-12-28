from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import psycopg2
from psycopg2.extras import RealDictCursor
import re
import requests
import json
import os
import time
import threading
import logging
import asyncio
from decimal import Decimal
from datetime import datetime, date
from pathlib import Path
from typing import List, Optional
from config import (
    POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_HOST,
    POSTGRES_PORT, DATABASE_NAME, OPENROUTER_API_KEY, OPENROUTER_URL
)
from data_generator import get_generator
from ml_pipeline import get_ml_pipeline
from ml_retrain_scheduler import get_retrain_scheduler
from chat_intelligence import get_chat_intelligence
from api_endpoints import router as api_router

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Tanker Data Management Chatbot API")

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API router
app.include_router(api_router, prefix="/api", tags=["api"])

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.pending_messages: List[dict] = []
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket connected. Total connections: {len(self.active_connections)}")
    
    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info(f"WebSocket disconnected. Total connections: {len(self.active_connections)}")
    
    def add_pending_message(self, message: dict):
        """Add message to pending queue (for background threads)"""
        self.pending_messages.append(message)
        # Keep only last 100 messages
        if len(self.pending_messages) > 100:
            self.pending_messages.pop(0)
    
    async def broadcast(self, message: dict):
        """Broadcast message to all connected clients"""
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"Error sending WebSocket message: {e}")
                disconnected.append(connection)
        
        # Remove disconnected clients
        for conn in disconnected:
            self.disconnect(conn)
    
    async def process_pending_messages(self):
        """Process pending messages from background threads"""
        if self.pending_messages:
            messages = self.pending_messages.copy()
            self.pending_messages.clear()
            for message in messages:
                await self.broadcast(message)

manager = ConnectionManager()

# Serve static files from frontend directory
frontend_path = Path(__file__).parent.parent / "frontend"
if frontend_path.exists():
    app.mount("/static", StaticFiles(directory=str(frontend_path)), name="static")
    
    @app.get("/")
    async def serve_index():
        """Serve the main HTML page"""
        index_path = frontend_path / "index.html"
        if index_path.exists():
            return FileResponse(str(index_path))
        raise HTTPException(status_code=404, detail="Frontend not found")
    
    @app.get("/dashboard.html")
    async def serve_dashboard():
        """Serve the dashboard page"""
        dashboard_path = frontend_path / "dashboard.html"
        if dashboard_path.exists():
            return FileResponse(str(dashboard_path))
        raise HTTPException(status_code=404, detail="Dashboard not found")
    
    @app.get("/tanker-details.html")
    async def serve_tanker_details():
        """Serve the tanker details page"""
        details_path = frontend_path / "tanker-details.html"
        if details_path.exists():
            return FileResponse(str(details_path))
        raise HTTPException(status_code=404, detail="Tanker details page not found")
    
    @app.get("/tanker-list.html")
    async def serve_tanker_list():
        """Serve the tanker list page"""
        list_path = frontend_path / "tanker-list.html"
        if list_path.exists():
            return FileResponse(str(list_path))
        raise HTTPException(status_code=404, detail="Tanker list page not found")
    
    @app.get("/chat.html")
    async def serve_chat():
        """Serve the chat page"""
        chat_path = frontend_path / "chat.html"
        if chat_path.exists():
            return FileResponse(str(chat_path))
        raise HTTPException(status_code=404, detail="Chat page not found")
    
    @app.get("/{filename}")
    async def serve_static(filename: str):
        """Serve static files (CSS, JS, etc.) - must be last route"""
        # Prevent serving HTML files through this route (they have dedicated routes)
        if filename.endswith('.html'):
            raise HTTPException(status_code=404, detail="File not found")
        
        file_path = frontend_path / filename
        if file_path.exists() and file_path.is_file():
            return FileResponse(str(file_path))
        raise HTTPException(status_code=404, detail="File not found")

class ChatRequest(BaseModel):
    message: str
    context: str = "full_chat"  # "dashboard" or "full_chat"
    chat_id: Optional[int] = None  # For feedback on previous chat
    feedback: Optional[str] = None  # "helpful" or "not_helpful"

class ChatResponse(BaseModel):
    response: str
    success: bool
    chat_id: Optional[int] = None  # Return chat_id for feedback
    intent: Optional[str] = None  # Detected intent
    followup_suggestions: Optional[List[str]] = None  # Suggested follow-up questions

def make_json_serializable(obj, format_dates=False):
    """Convert non-JSON-serializable objects to serializable types"""
    if isinstance(obj, Decimal):
        return float(obj)
    elif isinstance(obj, (datetime, date)):
        if format_dates:
            return format_datetime(obj)
        return obj.isoformat()
    elif isinstance(obj, str):
        # Check if string is an ISO timestamp and format it if needed
        if format_dates and ('T' in obj or (obj.count('-') >= 2 and '/' not in obj and len(obj) > 10)):
            try:
                return format_datetime(obj)
            except:
                return obj
    elif isinstance(obj, dict):
        return {key: make_json_serializable(value, format_dates) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [make_json_serializable(item, format_dates) for item in obj]
    elif isinstance(obj, tuple):
        return tuple(make_json_serializable(item, format_dates) for item in obj)
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

def fetch_tanker(tanker_id):
    """Fetch a single tanker record by tanker_id with related data"""
    conn = get_db_connection()
    if not conn:
        return None
    
    try:
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
                t.status_changed_at
            FROM tankers t
            LEFT JOIN drivers dr ON t.driver_id = dr.driver_id
            LEFT JOIN depots d ON t.source_depot_id = d.depot_id
            LEFT JOIN destinations dest ON t.destination_id = dest.destination_id
            WHERE LOWER(t.tanker_id) = LOWER(%s)
        """
        cursor.execute(query, (tanker_id,))
        record = cursor.fetchone()
        
        if record:
            tanker_data = dict(record)
            # Convert Decimal and other non-serializable types
            tanker_data = make_json_serializable(tanker_data)
            cursor.close()
            conn.close()
            return tanker_data
        else:
            cursor.close()
            conn.close()
            return None
    except Exception as e:
        logger.error(f"Error fetching tanker: {e}")
        if conn:
            conn.close()
        return None

def run_analytical_query(query_type, question):
    """Run SQL queries for analytical questions using normalized schema"""
    conn = get_db_connection()
    if not conn:
        return None
    
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        results = None
        
        # Detect query type and execute appropriate SQL
        question_lower = question.lower()
        
        if "active" in question_lower or "status" in question_lower:
            # Count by status
            cursor.execute("""
                SELECT current_status as status, COUNT(*) as count 
                FROM tankers 
                GROUP BY current_status;
            """)
            results = [dict(row) for row in cursor.fetchall()]
            
        elif "total" in question_lower or "how many" in question_lower:
            # Total count
            cursor.execute("SELECT COUNT(*) as total FROM tankers;")
            results = cursor.fetchone()['total']
            
        elif "summary" in question_lower or "overview" in question_lower:
            # Comprehensive summary
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_tankers,
                    COUNT(DISTINCT t.current_status) as unique_statuses,
                    COUNT(DISTINCT d.depot_name) as unique_depots,
                    SUM(CASE WHEN t.current_status = 'In Transit' THEN 1 ELSE 0 END) as in_transit,
                    SUM(CASE WHEN t.current_status = 'At Source' THEN 1 ELSE 0 END) as at_source,
                    SUM(CASE WHEN t.current_status = 'Delayed' THEN 1 ELSE 0 END) as delayed,
                    AVG(t.oil_volume_liters::numeric) as avg_volume,
                    AVG(t.trip_duration_hours::numeric) as avg_duration
                FROM tankers t
                LEFT JOIN depots d ON t.source_depot_id = d.depot_id;
            """)
            results = dict(cursor.fetchone())
            
        elif "depot" in question_lower or "source" in question_lower:
            # Group by depot
            cursor.execute("""
                SELECT d.depot_name as depot, COUNT(*) as count 
                FROM tankers t
                LEFT JOIN depots d ON t.source_depot_id = d.depot_id
                GROUP BY d.depot_name;
            """)
            results = [dict(row) for row in cursor.fetchall()]
            
        elif "destination" in question_lower:
            # Group by destination
            cursor.execute("""
                SELECT dest.destination_name as destination, COUNT(*) as count 
                FROM tankers t
                LEFT JOIN destinations dest ON t.destination_id = dest.destination_id
                GROUP BY dest.destination_name;
            """)
            results = [dict(row) for row in cursor.fetchall()]
            
        elif "seal" in question_lower:
            # Group by seal status
            cursor.execute("""
                SELECT seal_status, COUNT(*) as count 
                FROM tankers 
                GROUP BY seal_status;
            """)
            results = [dict(row) for row in cursor.fetchall()]
            
        else:
            # Default: return all records (limited to 50 for performance)
            cursor.execute("""
                SELECT 
                    t.tanker_id,
                    dr.driver_name,
                    t.current_status,
                    d.depot_name as source_depot,
                    dest.destination_name as destination
                FROM tankers t
                LEFT JOIN drivers dr ON t.driver_id = dr.driver_id
                LEFT JOIN depots d ON t.source_depot_id = d.depot_id
                LEFT JOIN destinations dest ON t.destination_id = dest.destination_id
                LIMIT 50;
            """)
            results = [dict(row) for row in cursor.fetchall()]
            
        cursor.close()
        conn.close()
        # Convert Decimal and other non-serializable types
        return make_json_serializable(results)
        
    except Exception as e:
        logger.error(f"Error running analytical query: {e}")
        if conn:
            conn.close()
        return None

def detect_tanker_id(question):
    """Detect if question contains a tanker ID (case-insensitive)"""
    # Pattern to match tanker IDs like TKR1008, TNK-001, TKR-1008, etc.
    patterns = [
        r'TKR-?\d+',           # TKR1008 or TKR-1008
        r'TNK-?\d+',           # TNK-001 or TNK001
        r'tanker\s+([A-Z0-9-]+)',  # "tanker TNK-001"
        r'tanker_id[:\s]+([A-Z0-9-]+)',  # "tanker_id: TNK-001"
        r'ID[:\s]+([A-Z0-9-]+)',  # "ID: TNK-001"
    ]
    
    for pattern in patterns:
        match = re.search(pattern, question, re.IGNORECASE)
        if match:
            tanker_id = match.group(1) if match.groups() else match.group(0)
            # Normalize to uppercase for consistency
            tanker_id = tanker_id.upper()
            # Normalize: if it's TKR followed by digits, add hyphen if missing
            if re.match(r'TKR\d+', tanker_id, re.IGNORECASE):
                tanker_id = re.sub(r'(TKR)(\d+)', r'\1-\2', tanker_id, flags=re.IGNORECASE)
            return tanker_id
    
    return None

def detect_user_intent(question):
    """Detect user intent for location vs coordinates"""
    question_lower = question.lower()
    
    # Keywords that indicate user wants coordinates
    coordinate_keywords = ['latitude', 'longitude', 'lat', 'long', 'lat long', 'lat/long', 
                          'coordinates', 'coordinate', 'exact location', 'gps', 'gps coordinates',
                          'lat lon', 'lat-lon']
    
    # Keywords that indicate user wants city name (default)
    location_keywords = ['where', 'location', 'city', 'place', 'current location', 
                        'where is', 'located', 'position']
    
    # Check for coordinate intent first (more specific)
    for keyword in coordinate_keywords:
        if keyword in question_lower:
            return 'coordinates'
    
    # Check for location intent
    for keyword in location_keywords:
        if keyword in question_lower:
            return 'city'
    
    # Default to city name
    return 'city'

def format_datetime(dt_string):
    """Format datetime string to DD/MM/YYYY HH:MM:SS - NEVER returns ISO format"""
    try:
        if isinstance(dt_string, str):
            # Check if already formatted (contains / and space)
            if '/' in dt_string and ' ' in dt_string and len(dt_string) > 10:
                # Already formatted, return as is
                return dt_string
            
            # Parse ISO format or other formats
            if 'T' in dt_string or dt_string.count('-') >= 2:
                # ISO format: 2025-12-28T08:23:06.474828 or 2025-12-28T08:23:06
                dt_string = dt_string.replace('Z', '+00:00')
                if '.' in dt_string:
                    # Remove microseconds
                    dt_string = dt_string.split('.')[0]
                dt = datetime.fromisoformat(dt_string)
            else:
                # Try other common formats
                dt = datetime.strptime(dt_string, '%Y-%m-%d %H:%M:%S')
        elif isinstance(dt_string, datetime):
            dt = dt_string
        elif isinstance(dt_string, date):
            dt = datetime.combine(dt_string, datetime.min.time())
        else:
            return str(dt_string)
        
        # Format as DD/MM/YYYY HH:MM:SS
        formatted = dt.strftime('%d/%m/%Y %H:%M:%S')
        return formatted
    except Exception as e:
        logger.warning(f"Error formatting datetime '{dt_string}': {e}")
        # If formatting fails, return a safe string instead of ISO
        return "Date unavailable"

def replace_iso_timestamps_in_text(text):
    """Replace any ISO timestamps in text with formatted dates"""
    import re
    # Pattern to match ISO timestamps: 2025-12-28T08:23:06.474828 or 2025-12-28T08:23:06
    iso_pattern = r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?)'
    
    def replace_timestamp(match):
        iso_str = match.group(1)
        try:
            formatted = format_datetime(iso_str)
            return formatted
        except:
            return iso_str
    
    # Replace all ISO timestamps in the text
    text = re.sub(iso_pattern, replace_timestamp, text)
    return text

def format_chat_response(text, context="full_chat"):
    """Format AI response to remove Markdown and ensure professional plain text"""
    if context != "full_chat":
        return text  # Only format full_chat responses
    
    import re
    
    # Remove Markdown bold (**text**)
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
    
    # Remove Markdown italic (*text* or _text_)
    text = re.sub(r'\*(.*?)\*', r'\1', text)
    text = re.sub(r'_(.*?)_', r'\1', text)
    
    # Remove Markdown headers (# Header)
    text = re.sub(r'^#{1,6}\s+(.*)$', r'\1', text, flags=re.MULTILINE)
    
    # Remove Markdown bullet points (- item or * item)
    text = re.sub(r'^[\s]*[-*+]\s+', '', text, flags=re.MULTILINE)
    
    # Remove Markdown numbered lists (1. item)
    text = re.sub(r'^\d+\.\s+', '', text, flags=re.MULTILINE)
    
    # Remove excessive emoji headers (keep only if used sparingly in context)
    # Remove standalone emoji lines
    text = re.sub(r'^[📍🕒🚛⛽📊]\s*$', '', text, flags=re.MULTILINE)
    
    # Clean up multiple consecutive newlines (max 2)
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    # Remove leading/trailing whitespace from each line
    lines = [line.strip() for line in text.split('\n')]
    text = '\n'.join(lines)
    
    # Remove empty lines at start and end
    text = text.strip()
    
    return text

def format_tanker_data_for_chat(tanker_data, user_intent='city'):
    """Format tanker data for professional chatbot response"""
    from city_mapper import get_city_from_coords
    
    formatted = {}
    
    for key, value in tanker_data.items():
        if value is None:
            continue
            
        # Format dates - catch all date/time fields
        if any(keyword in key.lower() for keyword in ['date', 'update', 'changed', 'time', 'at']):
            if isinstance(value, (datetime, date)) or (isinstance(value, str) and ('T' in value or value.count('-') >= 2)):
                formatted[key] = format_datetime(value)
            else:
                formatted[key] = value
        
        # Format location based on intent
        elif key == 'current_location_lat' or key == 'current_location_lon':
            if user_intent == 'coordinates':
                # Keep coordinates
                formatted[key] = value
            else:
                # Skip coordinates, will add city name instead
                continue
        
        # Format other fields
        else:
            formatted[key] = value
    
    # Add city name if location exists and intent is city
    if user_intent == 'city' and 'current_location_lat' in tanker_data and 'current_location_lon' in tanker_data:
        lat = tanker_data.get('current_location_lat')
        lon = tanker_data.get('current_location_lon')
        if lat and lon:
            city_name = get_city_from_coords(float(lat), float(lon))
            formatted['current_location'] = city_name
            formatted['current_location_city'] = city_name
    
    # Add coordinates if intent is coordinates
    if user_intent == 'coordinates' and 'current_location_lat' in tanker_data and 'current_location_lon' in tanker_data:
        lat = tanker_data.get('current_location_lat')
        lon = tanker_data.get('current_location_lon')
        if lat and lon:
            formatted['current_location_latitude'] = float(lat)
            formatted['current_location_longitude'] = float(lon)
    
    return formatted

def generate_fallback_response(user_question, data_context, context="full_chat"):
    """Generate a fallback response when API is unavailable"""
    question_lower = user_question.lower()
    user_intent = detect_user_intent(user_question)
    
    # For dashboard context, provide concise fallback
    if context == "dashboard":
        if isinstance(data_context, dict):
            # Single tanker - concise format
            response = f"Tanker {data_context.get('tanker_id', 'N/A')}: {data_context.get('current_status', 'N/A')}"
            if data_context.get('current_location'):
                response += f" at {data_context.get('current_location')}"
            return response
        else:
            # Ambiguous - provide options
            return "I can help with:\n- Delayed tankers\n- Tankers by city\n- Delivery status\n- ETA for a specific tanker"
    
    if isinstance(data_context, dict):
        # Single tanker data - format professionally
        formatted_data = format_tanker_data_for_chat(data_context, user_intent)
        # Ensure all dates are formatted (double-check for any ISO strings)
        serializable_data = make_json_serializable(formatted_data, format_dates=True)
        
        response = "**Tanker Details:**\n\n"
        
        # Format location based on intent
        if user_intent == 'coordinates' and 'current_location_latitude' in serializable_data:
            response += f"📍 **Exact Location:**\n"
            response += f"Latitude: {serializable_data.get('current_location_latitude')}\n"
            response += f"Longitude: {serializable_data.get('current_location_longitude')}\n\n"
        elif 'current_location' in serializable_data or 'current_location_city' in serializable_data:
            city = serializable_data.get('current_location') or serializable_data.get('current_location_city')
            response += f"📍 **Current Location:** {city}\n\n"
        
        # Format other fields
        for key, value in serializable_data.items():
            if value is not None and key not in ['current_location_lat', 'current_location_lon', 
                                                  'current_location_latitude', 'current_location_longitude',
                                                  'current_location', 'current_location_city']:
                # Format field name
                field_name = key.replace('_', ' ').title()
                # Double-check date formatting - ensure no ISO timestamps slip through
                if any(keyword in key.lower() for keyword in ['date', 'update', 'changed', 'time']):
                    if isinstance(value, str) and ('T' in value or (value.count('-') >= 2 and '/' not in value)):
                        value = format_datetime(value)
                    response += f"🕒 **{field_name}:** {value}\n"
                else:
                    response += f"• **{field_name}:** {value}\n"
        
        return response
    
    elif isinstance(data_context, list) and len(data_context) > 0:
        # List of records
        if isinstance(data_context[0], dict):
            # Convert to serializable format
            serializable_list = make_json_serializable(data_context)
            response = f"**Query Results:**\n\n"
            for item in serializable_list[:10]:  # Limit to 10 items
                response += f"• {json.dumps(item, indent=2)}\n\n"
            if len(serializable_list) > 10:
                response += f"\n*Showing 10 of {len(serializable_list)} results*"
            return response
        else:
            return f"**Result:** {data_context}"
    
    elif isinstance(data_context, (int, float, str)):
        # Simple value
        return f"**Answer:** {data_context}"
    
    else:
        # Convert to serializable format
        serializable_data = make_json_serializable(data_context)
        return f"Here is the data:\n\n{json.dumps(serializable_data, indent=2)}"

def get_ml_insights(tanker_id):
    """Get ML predictions and insights for a tanker"""
    try:
        ml_pipeline = get_ml_pipeline()
        insights = {}
        
        # Get arrival time prediction
        arrival_time = ml_pipeline.predict_arrival_time(tanker_id)
        if arrival_time is not None:
            insights['predicted_arrival_time_hours'] = round(arrival_time, 2)
        
        # Get delay probability
        delay_prob = ml_pipeline.predict_delay_probability(tanker_id)
        if delay_prob is not None:
            insights['delay_probability'] = round(delay_prob, 4)
            insights['delay_risk'] = 'High' if delay_prob > 0.7 else 'Medium' if delay_prob > 0.4 else 'Low'
        
        return insights
    except Exception as e:
        logger.error(f"Error getting ML insights: {e}")
        return {}

def call_openrouter_api(user_question, data_context=None, ml_insights=None, context="full_chat", max_retries=3):
    """Call OpenRouter API to generate natural language response with retry logic"""
    # Check if API key is available
    if not OPENROUTER_API_KEY or OPENROUTER_API_KEY == "":
        logger.warning("OPENROUTER_API_KEY not set, using fallback response")
        if data_context:
            return generate_fallback_response(user_question, data_context, context)
        else:
            if context == "dashboard":
                return "I can help with: delayed tankers, tankers by city, delivery status, ETA for a specific tanker."
            return "I'm currently unable to access the AI service. Please ensure the OPENROUTER_API_KEY is configured. However, I can still help you with basic questions about tanker data. Try asking: 'How many tankers are there?' or 'What is the status summary?'"
    
    try:
        logger.info(f"Calling OpenRouter API with question (context: {context}): {user_question[:100]}...")
        # Detect user intent
        user_intent = detect_user_intent(user_question)
        
        # Build context-specific system message
        if context == "dashboard":
            system_message = """You are a concise AI assistant for tanker data management on a dashboard widget.

CRITICAL RULES FOR DASHBOARD CONTEXT:
1. RESPONSE LENGTH: Maximum 2-4 lines. Be extremely brief and direct.
2. NO EXPLANATIONS: Answer only what is explicitly asked. No step-by-step guides, no background context.
3. NO PREDICTIONS: Do NOT provide ML predictions, forecasts, or estimates UNLESS the user explicitly asks with words like: "predict", "forecast", "estimate", "future", "likely", "probability".
4. FORMATTING: Use city names (e.g., "Lahore, Pakistan"), dates as DD/MM/YYYY HH:MM:SS. Use emojis sparingly (📍 🕒).
5. AMBIGUOUS QUESTIONS: If the question is unclear or incomplete, respond with 2-4 short options:
   "I can help with:
   - Delayed tankers
   - Tankers by city
   - Delivery status
   - ETA for a specific tanker"
6. DIRECT ANSWERS: "5 tankers are delayed near Multan." NOT "Based on the data analysis, I found that there are currently 5 tankers that are experiencing delays in the Multan area..."

Example good response: "3 tankers in transit. 2 delayed near Karachi."
Example bad response: "Let me analyze the current tanker status. Based on the data I have access to, there are currently 3 tankers that are in transit, and 2 tankers that are experiencing delays near Karachi..."."""
        else:
            # Full chat context - detailed and analytical
            system_message = """You are a professional operations analyst for a tanker logistics monitoring system. You provide clear, realistic reports based on real-time data.

CRITICAL FORMATTING RULES (MANDATORY):
1. NO MARKDOWN: Do NOT use **, *, bullet points, or any Markdown formatting. Write in plain text only.
2. NO SYMBOLS: Do NOT use emoji headers, asterisks, or special formatting symbols. Use plain text headings if needed.
3. PLAIN TEXT PARAGRAPHS: Write in clear, natural paragraphs. Use line breaks between paragraphs only.
4. PROFESSIONAL TONE: Write like a real logistics operations report. Be factual, concise, and professional.
5. LOCATION: Use city name format (e.g., "Lahore, Punjab" or "near Faisalabad"). Do NOT use coordinates unless explicitly requested.
6. DATES: Format as "DD Month YYYY at HH:MM" (e.g., "28 December 2025 at 13:45"). NEVER use ISO format.
7. REALISTIC LANGUAGE: Use natural, professional language. Avoid repetitive phrases. Do NOT restate the same information multiple times.
8. DATA ACCURACY: Only mention data that exists. If data is unavailable, state it clearly: "The [field] is currently unavailable."
9. RESPONSE LENGTH: Keep responses to 3-5 short paragraphs maximum. Be comprehensive but concise.

EXAMPLE OF CORRECT STYLE:
Tanker 016 is currently operating normally.

It is being driven by Usman Butt and was last reported near Faisalabad, Punjab at 13:45 on 28 December 2025. The tanker is sealed and carrying approximately 18,674 liters of oil against a maximum capacity of 22,000 liters.

The tanker is en route to Shell Pakistan Limited and has been in transit for just under two hours, maintaining an average speed of around 61 km/h. Based on current conditions, there are no signs of delay or operational risk.

EXAMPLE OF INCORRECT STYLE (DO NOT USE):
**Tanker Status Report**

• Tanker ID: 016
• Driver: **Usman Butt**
• Location: 📍 Faisalabad

The tanker is currently:
- In transit
- Sealed
- Carrying oil

**Summary:** Everything is normal."""
        
        user_message = user_question
        
        if data_context:
            # Format data context based on user intent
            if isinstance(data_context, dict):
                # Single tanker - format it (dates already formatted in format_tanker_data_for_chat)
                formatted_context = format_tanker_data_for_chat(data_context, user_intent)
                # Make serializable - format any remaining ISO timestamps
                serializable_context = make_json_serializable(formatted_context, format_dates=True)
            else:
                # Other data types - format dates during serialization
                serializable_context = make_json_serializable(data_context, format_dates=True)
            
            # Format data context for the AI
            context_str = f"\n\nHere is the relevant data from the database:\n{json.dumps(serializable_context, indent=2)}"
            user_message = user_question + context_str
        
        # Only include ML insights for full_chat context or if explicitly requested
        should_include_ml = context == "full_chat" or any(keyword in user_question.lower() for keyword in ['predict', 'forecast', 'estimate', 'future', 'likely', 'probability'])
        if ml_insights and should_include_ml:
            # Convert to JSON-serializable format
            serializable_insights = make_json_serializable(ml_insights)
            # Add ML insights to context
            insights_str = f"\n\nMachine Learning Predictions:\n{json.dumps(serializable_insights, indent=2)}"
            user_message = user_message + insights_str
        
        payload = {
            "model": "meta-llama/llama-3.2-3b-instruct:free",
            "messages": [
                {"role": "system", "content": system_message},
                {"role": "user", "content": user_message}
            ]
        }
        
        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://tanker-chatbot.onrender.com",
            "X-Title": "Tanker Data Management Chatbot"
        }
        
        # Retry logic with exponential backoff
        for attempt in range(max_retries):
            try:
                response = requests.post(
                    url=OPENROUTER_URL,
                    headers=headers,
                    data=json.dumps(payload),
                    timeout=30
                )
                
                if response.status_code == 200:
                    result = response.json()
                    content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
                    if content:
                        logger.info(f"OpenRouter API returned response (length: {len(content)})")
                        # Post-process to replace any ISO timestamps that might have slipped through
                        content = replace_iso_timestamps_in_text(content)
                        # Format response to remove Markdown (for full_chat context)
                        content = format_chat_response(content, context)
                        return content
                    else:
                        logger.warning("OpenRouter API returned empty content")
                        if data_context:
                            return generate_fallback_response(user_question, data_context)
                        return "Sorry, I couldn't generate a response. Please try rephrasing your question."
                
                elif response.status_code == 429:
                    # Rate limited - wait and retry
                    if attempt < max_retries - 1:
                        wait_time = (2 ** attempt) * 2  # Exponential backoff: 2s, 4s, 8s
                        logger.info(f"Rate limited (429). Retrying in {wait_time} seconds... (Attempt {attempt + 1}/{max_retries})")
                        time.sleep(wait_time)
                        continue
                    else:
                        # Max retries reached, use fallback
                        logger.warning("Max retries reached for rate limiting. Using fallback response.")
                        if data_context:
                            fallback = generate_fallback_response(user_question, data_context)
                            return f"⚠️ **API Rate Limit Reached**\n\nThe OpenRouter API is currently rate-limited. Here's the data I found:\n\n{fallback}\n\n*Please try again in a few moments for an AI-generated summary.*"
                        else:
                            return "⚠️ **API Rate Limit Reached**\n\nThe OpenRouter API is currently rate-limited. Please try again in a few moments."
                
                elif response.status_code == 401:
                    return "❌ **Authentication Error**\n\nInvalid API key. Please check your OpenRouter API key configuration."
                
                elif response.status_code == 402:
                    return "❌ **Payment Required**\n\nThe API requires payment. Please check your OpenRouter account balance."
                
                elif response.status_code == 404:
                    # Model not found - use fallback if we have data
                    logger.warning("OpenRouter API error: Model not found (404). Using fallback response.")
                    if data_context and attempt == max_retries - 1:
                        fallback = generate_fallback_response(user_question, data_context)
                        return fallback
                    elif attempt == max_retries - 1:
                        return f"❌ **Model Not Found**\n\nThe requested AI model is not available. Please check the model configuration."
                
                else:
                    # Other errors - try fallback if we have data
                    logger.error(f"OpenRouter API error: {response.status_code} - {response.text}")
                    if data_context and attempt == max_retries - 1:
                        fallback = generate_fallback_response(user_question, data_context)
                        # Show data prominently, with subtle note about API
                        return f"{fallback}\n\n*Note: AI enhancement unavailable (Status: {response.status_code})*"
                    elif attempt == max_retries - 1:
                        return f"❌ **API Error**\n\nCould not get AI response. Status: {response.status_code}\n\nError details: {response.text[:200]}"
                    else:
                        # Retry for other errors too
                        wait_time = (2 ** attempt) * 1
                        time.sleep(wait_time)
                        continue
                        
            except requests.exceptions.Timeout:
                if attempt < max_retries - 1:
                    wait_time = (2 ** attempt) * 1
                    logger.warning(f"Request timeout. Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                    continue
                else:
                    if data_context:
                        fallback = generate_fallback_response(user_question, data_context)
                        return f"⏱️ **Request Timeout**\n\nThe API request timed out. Here's the data I found:\n\n{fallback}"
                    else:
                        return "⏱️ **Request Timeout**\n\nThe API request timed out. Please try again."
            
            except requests.exceptions.RequestException as e:
                if attempt < max_retries - 1:
                    wait_time = (2 ** attempt) * 1
                    logger.warning(f"Request error: {e}. Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                    continue
                else:
                    if data_context:
                        fallback = generate_fallback_response(user_question, data_context)
                        return f"❌ **Connection Error**\n\nCould not connect to the API. Here's the data I found:\n\n{fallback}"
                    else:
                        return f"❌ **Connection Error**\n\nCould not connect to the API: {str(e)}"
        
        # Should not reach here, but just in case
        if data_context:
            fallback = generate_fallback_response(user_question, data_context)
            return f"Here's the data I found:\n\n{fallback}"
        else:
            return "Sorry, I couldn't process your request. Please try again."
            
    except Exception as e:
        logger.error(f"Error calling OpenRouter API: {e}")
        if data_context:
            fallback = generate_fallback_response(user_question, data_context)
            return f"❌ **Error**\n\nAn error occurred: {str(e)}\n\nHere's the data I found:\n\n{fallback}"
        else:
            return f"❌ **Error**\n\nAn unexpected error occurred: {str(e)}"
            return f"❌ **Error**\n\nAn unexpected error occurred: {str(e)}"

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Main chat endpoint with ML integration and Chat Intelligence"""
    try:
        user_question = request.message.strip()
        context = request.context or "full_chat"  # Default to full_chat if not provided
        logger.info(f"Received chat request (context: {context}): {user_question[:100]}...")
        
        # Handle feedback if provided
        if request.feedback and request.chat_id:
            chat_intel = get_chat_intelligence()
            feedback_type = 'explicit_helpful' if request.feedback == 'helpful' else 'explicit_not_helpful'
            feedback_value = 1 if request.feedback == 'helpful' else 0
            chat_intel.record_feedback(request.chat_id, feedback_type, feedback_value)
            return ChatResponse(
                response="Thank you for your feedback!",
                success=True
            )
        
        if not user_question:
            return ChatResponse(
                response="Please provide a message.",
                success=False
            )
        
        # Initialize Chat Intelligence
        chat_intel = get_chat_intelligence()
        
        # Step 1: Classify intent and topic using Chat Intelligence
        intent, confidence = chat_intel.classify_intent(user_question)
        logger.info(f"Chat Intelligence: intent={intent}, confidence={confidence:.2f}")
        
        # Step 2: Check if question contains a tanker_id
        tanker_id = detect_tanker_id(user_question)
        ml_insights = None
        logger.info(f"Detected tanker_id: {tanker_id}")
        
        # Step 3: Get topic classification
        topic = chat_intel.classify_topic(user_question, tanker_id)
        
        # Step 4: Check for similar questions and get suggestions
        similar_questions = chat_intel.find_similar_questions(user_question, limit=3)
        response_suggestions = chat_intel.get_improved_response_suggestions(user_question, intent)
        
        # For dashboard context, only get ML insights if explicitly requested
        question_lower = user_question.lower()
        should_get_ml = context == "full_chat" or any(keyword in question_lower for keyword in ['predict', 'forecast', 'estimate', 'future', 'likely', 'probability'])
        
        # If intent suggests prediction/trend, enable ML insights
        if intent in ['trend_analysis', 'eta_inquiry'] or topic == 'prediction_request':
            should_get_ml = True
        
        try:
            if tanker_id:
                # Fetch specific tanker data
                tanker_data = fetch_tanker(tanker_id)
                if tanker_data:
                    # Get ML insights only if needed (Tanker Analytics ML)
                    if should_get_ml:
                        try:
                            ml_insights = get_ml_insights(tanker_id)
                        except Exception as e:
                            logger.warning(f"Could not get ML insights: {e}")
                            ml_insights = None
                    
                    # Generate response with tanker data and ML insights
                    response_text = call_openrouter_api(user_question, tanker_data, ml_insights, context)
                else:
                    response_text = f"Sorry, I couldn't find a tanker with ID '{tanker_id}'. Please check the ID and try again."
            else:
                # Step 5: Run analytical query
                try:
                    query_results = run_analytical_query("auto", user_question)
                except Exception as e:
                    logger.warning(f"Could not run analytical query: {e}")
                    query_results = None
                
                if query_results is not None:
                    # Generate response with query results
                    response_text = call_openrouter_api(user_question, query_results, ml_insights, context)
                else:
                    # Fallback: just ask AI without data
                    response_text = call_openrouter_api(user_question, None, ml_insights, context)
            
            # Step 6: Store chat interaction for learning
            response_metadata = {
                'similar_questions_found': len(similar_questions),
                'response_suggestions_used': response_suggestions is not None,
                'tanker_ml_used': ml_insights is not None
            }
            
            chat_id = chat_intel.store_chat_interaction(
                user_message=user_question,
                bot_response=response_text,
                context=context,
                tanker_id=tanker_id,
                intent=intent,
                topic=topic,
                confidence=confidence,
                response_metadata=response_metadata
            )
            
            # Step 7: Get follow-up suggestions
            followup_suggestions = chat_intel.get_followup_suggestions(user_question, intent, topic)
            
            return ChatResponse(
                response=response_text,
                success=True,
                chat_id=chat_id,
                intent=intent,
                followup_suggestions=followup_suggestions
            )
            
        except Exception as e:
            logger.error(f"Error processing chat request: {e}", exc_info=True)
            # Store error interaction for learning
            try:
                chat_intel.store_chat_interaction(
                    user_message=user_question,
                    bot_response=f"Error: {str(e)}",
                    context=context,
                    tanker_id=tanker_id,
                    intent=intent,
                    topic=topic,
                    confidence=confidence
                )
            except:
                pass
            
            # Return a helpful error message instead of crashing
            return ChatResponse(
                response=f"I encountered an error while processing your request: {str(e)}. Please try rephrasing your question or try again later.",
                success=False
            )
        
    except Exception as e:
        logger.error(f"Error in chat endpoint: {e}", exc_info=True)
        return ChatResponse(
            response=f"An unexpected error occurred: {str(e)}. Please try again.",
            success=False
        )

@app.post("/chat/feedback")
async def chat_feedback(chat_id: int, feedback_type: str, feedback_value: Optional[int] = None):
    """Record feedback for a chat interaction"""
    try:
        chat_intel = get_chat_intelligence()
        success = chat_intel.record_feedback(chat_id, feedback_type, feedback_value)
        
        if success:
            return {"success": True, "message": "Feedback recorded"}
        else:
            return {"success": False, "message": "Failed to record feedback"}
    except Exception as e:
        logger.error(f"Error recording feedback: {e}")
        return {"success": False, "message": str(e)}

@app.get("/health")
async def health():
    """Health check endpoint for Render and monitoring"""
    return {
        'status': 'ok',
        'timestamp': datetime.now().isoformat(),
        'service': 'tanker-chatbot'
    }

@app.get("/api/health")
async def api_health():
    """Detailed health check endpoint"""
    # Lazy-load generator check to avoid unnecessary initialization
    try:
        generator = get_generator()
        generator_status = 'running' if generator.running else 'stopped'
    except Exception:
        generator_status = 'unknown'
    
    return {
        'status': 'healthy', 
        'service': 'tanker-chatbot',
        'data_generator': generator_status,
        'timestamp': datetime.now().isoformat()
    }

@app.websocket("/ws/tankers")
async def websocket_tankers(websocket: WebSocket):
    """WebSocket endpoint for real-time tanker updates"""
    await manager.connect(websocket)
    try:
        # Process any pending messages first
        await manager.process_pending_messages()
        
        while True:
            # Process pending messages periodically
            await manager.process_pending_messages()
            
            # Keep connection alive and wait for client messages
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=1.0)
                # Echo back or handle client messages if needed
                await websocket.send_json({"type": "pong", "message": "Connection active"})
            except asyncio.TimeoutError:
                # Timeout is expected, continue to process pending messages
                continue
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket)

def initialize_services():
    """Initialize background services - optimized for fast startup"""
    try:
        # Start data generator (non-blocking)
        generator = get_generator()
        generator.start()
        logger.info("Data generator started")
        
        # ML models are now lazy-loaded - only load when prediction endpoints are called
        # This significantly reduces startup time
        logger.info("ML pipeline will load models on-demand")
        
        # Start ML retrain scheduler (non-blocking)
        retrain_scheduler = get_retrain_scheduler()
        retrain_scheduler.start()
        logger.info("ML retrain scheduler started")
        
        # Schedule initial ML training (in background thread)
        # Wait longer to allow data generator to create enough samples
        def train_models_async():
            from config import DATA_GENERATION_INTERVAL, ML_MIN_SAMPLES_FOR_TRAINING
            # Wait for at least enough time to generate minimum samples
            # Each cycle generates 1-3 tankers, so we need several cycles
            wait_time = max(60, DATA_GENERATION_INTERVAL * (ML_MIN_SAMPLES_FOR_TRAINING // 2))
            logger.info(f"ML training will start after {wait_time} seconds to allow data accumulation...")
            time.sleep(wait_time)
            try:
                ml_pipeline = get_ml_pipeline()
                ml_pipeline.train_all_models()
            except Exception as e:
                logger.error(f"Error in initial ML training: {e}")
        
        training_thread = threading.Thread(target=train_models_async, daemon=True)
        training_thread.start()
        
    except Exception as e:
        logger.error(f"Error initializing services: {e}")

# Initialize services on startup
@app.on_event("startup")
async def startup_event():
    logger.info("Starting Tanker Data Management Chatbot...")
    
    # Database initialization in background thread to avoid blocking startup
    def init_db_async():
        try:
            from init_db import init_database
            logger.info("Checking database initialization...")
            init_database()
        except Exception as e:
            logger.warning(f"Database initialization check failed: {e}")
            logger.warning("Continuing anyway - make sure database is set up manually if needed.")
    
    # Run database check in background to avoid blocking startup
    db_thread = threading.Thread(target=init_db_async, daemon=True)
    db_thread.start()
    
    # Initialize services (non-blocking)
    initialize_services()
    
    logger.info("Server ready - health check available at /health")

if __name__ == '__main__':
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    logger.info(f"📡 Backend API starting on port {port}")
    logger.info(f"📡 Health check available at /health")
    uvicorn.run(app, host="0.0.0.0", port=port)