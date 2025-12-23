from fastapi import FastAPI, HTTPException
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
from decimal import Decimal
from datetime import datetime, date
from pathlib import Path
from config import (
    POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_HOST,
    POSTGRES_PORT, DATABASE_NAME, OPENROUTER_API_KEY, OPENROUTER_URL
)
from data_generator import get_generator
from ml_pipeline import get_ml_pipeline
from ml_retrain_scheduler import get_retrain_scheduler
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
    
    @app.get("/styles.css")
    async def serve_styles():
        """Serve the CSS file"""
        css_path = frontend_path / "styles.css"
        if css_path.exists():
            return FileResponse(str(css_path))
        raise HTTPException(status_code=404, detail="CSS not found")
    
    @app.get("/script.js")
    async def serve_script():
        """Serve the JavaScript file"""
        js_path = frontend_path / "script.js"
        if js_path.exists():
            return FileResponse(str(js_path))
        raise HTTPException(status_code=404, detail="JavaScript not found")

class ChatRequest(BaseModel):
    message: str

class ChatResponse(BaseModel):
    response: str
    success: bool

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
        print(f"Database connection error: {e}")
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

def generate_fallback_response(user_question, data_context):
    """Generate a fallback response when API is unavailable"""
    question_lower = user_question.lower()
    
    if isinstance(data_context, dict):
        # Single tanker data
        # Convert to serializable format first
        serializable_data = make_json_serializable(data_context)
        response = f"**Tanker Details:**\n\n"
        for key, value in serializable_data.items():
            if value is not None:
                response += f"• **{key.replace('_', ' ').title()}**: {value}\n"
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

def call_openrouter_api(user_question, data_context=None, ml_insights=None, max_retries=3):
    """Call OpenRouter API to generate natural language response with retry logic"""
    try:
        # Build context message
        system_message = """You are a helpful AI assistant for tanker data management. 
You help users understand tanker operations, analyze data, and provide insights.
You have access to real-time data and machine learning predictions.
Be concise, clear, and professional in your responses.
When ML predictions are available, incorporate them naturally into your answers."""
        
        user_message = user_question
        
        if data_context:
            # Convert to JSON-serializable format
            serializable_context = make_json_serializable(data_context)
            # Format data context for the AI
            context_str = f"\n\nHere is the relevant data from the database:\n{json.dumps(serializable_context, indent=2)}"
            user_message = user_question + context_str
        
        if ml_insights:
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
                    return result.get("choices", [{}])[0].get("message", {}).get("content", "Sorry, I couldn't generate a response.")
                
                elif response.status_code == 429:
                    # Rate limited - wait and retry
                    if attempt < max_retries - 1:
                        wait_time = (2 ** attempt) * 2  # Exponential backoff: 2s, 4s, 8s
                        print(f"Rate limited (429). Retrying in {wait_time} seconds... (Attempt {attempt + 1}/{max_retries})")
                        time.sleep(wait_time)
                        continue
                    else:
                        # Max retries reached, use fallback
                        print("Max retries reached for rate limiting. Using fallback response.")
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
                    print(f"OpenRouter API error: Model not found (404). Using fallback response.")
                    if data_context and attempt == max_retries - 1:
                        fallback = generate_fallback_response(user_question, data_context)
                        return fallback
                    elif attempt == max_retries - 1:
                        return f"❌ **Model Not Found**\n\nThe requested AI model is not available. Please check the model configuration."
                
                else:
                    # Other errors - try fallback if we have data
                    print(f"OpenRouter API error: {response.status_code} - {response.text}")
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
                    print(f"Request timeout. Retrying in {wait_time} seconds...")
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
                    print(f"Request error: {e}. Retrying in {wait_time} seconds...")
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
        print(f"Error calling OpenRouter API: {e}")
        if data_context:
            fallback = generate_fallback_response(user_question, data_context)
            return f"❌ **Error**\n\nAn error occurred: {str(e)}\n\nHere's the data I found:\n\n{fallback}"
        else:
            return f"❌ **Error**\n\nAn unexpected error occurred: {str(e)}"

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Main chat endpoint with ML integration"""
    try:
        user_question = request.message.strip()
        
        if not user_question:
            raise HTTPException(status_code=400, detail="Message is required")
        
        # Step 1: Check if question contains a tanker_id
        tanker_id = detect_tanker_id(user_question)
        ml_insights = None
        
        if tanker_id:
            # Fetch specific tanker data
            tanker_data = fetch_tanker(tanker_id)
            if tanker_data:
                # Get ML insights for predictions
                question_lower = user_question.lower()
                if any(keyword in question_lower for keyword in ['when', 'arrival', 'delay', 'predict', 'likely', 'probability']):
                    ml_insights = get_ml_insights(tanker_id)
                
                # Generate response with tanker data and ML insights
                response_text = call_openrouter_api(user_question, tanker_data, ml_insights)
            else:
                response_text = f"Sorry, I couldn't find a tanker with ID '{tanker_id}'. Please check the ID and try again."
        else:
            # Step 2: Run analytical query
            query_results = run_analytical_query("auto", user_question)
            
            if query_results is not None:
                # Generate response with query results
                response_text = call_openrouter_api(user_question, query_results, ml_insights)
            else:
                # Fallback: just ask AI without data
                response_text = call_openrouter_api(user_question, None, ml_insights)
        
        return ChatResponse(
            response=response_text,
            success=True
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in chat endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/health")
async def health():
    """Health check endpoint"""
    return {
        'status': 'healthy', 
        'service': 'tanker-chatbot',
        'data_generator': 'running' if get_generator().running else 'stopped'
    }

def initialize_services():
    """Initialize background services"""
    try:
        # Start data generator
        generator = get_generator()
        generator.start()
        logger.info("✅ Data generator started")
        
        # Load ML models
        ml_pipeline = get_ml_pipeline()
        ml_pipeline.load_models()
        logger.info("✅ ML pipeline initialized")
        
        # Start ML retrain scheduler
        retrain_scheduler = get_retrain_scheduler()
        retrain_scheduler.start()
        logger.info("✅ ML retrain scheduler started")
        
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
    logger.info("🚀 Starting Tanker Data Management Chatbot...")
    initialize_services()

if __name__ == '__main__':
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    logger.info(f"📡 Backend API running on http://localhost:{port}")
    logger.info(f"📡 Access the frontend at: http://localhost:{port}/")
    logger.info(f"📡 API health check: http://localhost:{port}/api/health")
    uvicorn.run(app, host="0.0.0.0", port=port)
