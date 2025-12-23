# Tanker Data Management System - Enterprise Edition

A comprehensive tanker management system with real-time data generation, machine learning predictions, and an AI-powered chatbot. The system features automatic status transitions, continuous ML learning, and a normalized PostgreSQL database.

## 🚀 Features

### Core Features
- **Real-time Data Generation**: Background service generates realistic tanker data every 30 seconds
- **Automatic Status Transitions**: Tankers automatically transition between states (e.g., In Transit → Reached Destination)
- **Normalized Database**: PostgreSQL schema with proper relationships and indexes
- **RESTful API**: Comprehensive API endpoints for tanker operations
- **Machine Learning Pipeline**: Continuous learning from data with predictions for:
  - Arrival time estimation
  - Delay probability
  - Status transition prediction
- **AI Chatbot**: Enhanced chatbot that uses ML insights for better answers
- **Historical Tracking**: Complete time-series history of all tanker operations

### New Features (Extended Version)
- **Background Data Generator**: Realistic tanker data generation every 30 seconds
- **Status Transition Logic**: Deterministic, time-based status changes
- **ML Predictions**: Real-time predictions for operational questions
- **Continuous Learning**: Models retrain automatically as data accumulates
- **Scalable Architecture**: Modular design for enterprise deployment

## 📋 Prerequisites

1. **Python 3.8+** installed on your system
2. **PostgreSQL 12+** installed and running
3. **PostgreSQL Development Libraries** (for psycopg2)

## 🔧 Installation

### 1. Clone/Download the Project

```bash
cd "D:\Azfar Project - Copy"
```

### 2. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Environment Variables

Create a `.env` file (or copy from `.env.example`):

```bash
cp .env.example .env
```

Edit `.env` with your configuration:
```env
POSTGRES_USER=postgres
POSTGRES_PASSWORD=root
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
DATABASE_NAME=tankerdb
```

### 4. Setup Database

Run the database setup script to create the normalized schema:

```bash
python setup_database.py
```

This will:
- Create the `tankerdb` database (if it doesn't exist)
- Create all normalized tables (tankers, drivers, depots, destinations, history, ML tables)
- Set up indexes for optimal performance
- Insert initial reference data

## 🏃 Running the Application

### Start the Backend

```bash
python app.py
```

The application will:
- Start the Flask API server on `http://localhost:5000`
- Initialize the background data generator (runs every 30 seconds)
- Start the status transition processor (runs every 5 minutes)
- Load existing ML models (if available)
- Schedule initial ML training after data accumulates

### Access the Frontend

1. Open `index.html` in your web browser, or
2. Use a local server:
   ```bash
   python -m http.server 8000
   ```
   Then navigate to `http://localhost:8000`

## 📡 API Endpoints

### Chat Endpoint
**POST** `/api/chat`
Main chatbot endpoint with ML integration.

**Request:**
```json
{
  "message": "When will TNK-001 reach destination?"
}
```

**Response:**
```json
{
  "response": "Based on current data and ML predictions...",
  "success": true
}
```

### Tanker Operations

**GET** `/api/tankers`
Get all tankers with optional filters:
- `?status=In Transit` - Filter by status
- `?depot=Islamabad` - Filter by depot
- `?limit=50&offset=0` - Pagination

**GET** `/api/tankers/<tanker_id>`
Get specific tanker details

**GET** `/api/tankers/<tanker_id>/status`
Get current status of a tanker

**GET** `/api/tankers/<tanker_id>/history`
Get historical records for a tanker
- `?days=30` - Number of days of history
- `?limit=100` - Maximum records

**GET** `/api/tankers/<tanker_id>/predictions`
Get ML predictions for a tanker (arrival time, delay probability)

### Statistics

**GET** `/api/stats`
Get overall statistics about tankers

**GET** `/api/health`
Health check endpoint

## 💬 Chatbot Usage Examples

### Tanker-Specific Queries (with ML Predictions)
- "When will TNK-001 reach destination?"
- "What is the delay probability for TNK-002?"
- "Show me details of tanker TNK-003"
- "Which tanker is likely to be delayed?"

### Analytical Queries
- "How many tankers are active?"
- "How many tankers are in transit?"
- "Give me a summary of tanker operations"
- "How many tankers are at each depot?"
- "What is the seal status distribution?"

### ML-Enhanced Queries
- "Predict arrival time for TNK-001"
- "Which tankers have high delay risk?"
- "What's the average transit time?"

## 🏗️ Architecture

### Database Schema

The system uses a normalized PostgreSQL schema:

- **tankers**: Current state of all tankers
- **tanker_history**: Time-series historical records
- **drivers**: Driver information
- **depots**: Depot locations and details
- **destinations**: Destination information
- **ml_model_metadata**: ML model versions and metrics
- **ml_predictions**: Stored predictions

### Components

1. **Data Generator** (`data_generator.py`)
   - Generates realistic tanker data every 30 seconds
   - Manages automatic status transitions
   - Maintains historical records

2. **ML Pipeline** (`ml_pipeline.py`)
   - Trains models on historical data
   - Provides predictions (arrival time, delays, transitions)
   - Stores model metadata and predictions

3. **API Layer** (`api_endpoints.py`)
   - RESTful endpoints for all operations
   - Integrates with ML pipeline for predictions

4. **Chatbot** (`app.py`)
   - Enhanced with ML insights
   - Natural language interface
   - Real-time data queries

5. **ML Retrain Scheduler** (`ml_retrain_scheduler.py`)
   - Periodic model retraining
   - Continuous learning from new data

## ⚙️ Configuration

All configuration is managed through environment variables (see `.env.example`):

- **Database**: Connection settings
- **Data Generation**: Intervals for data generation and status transitions
- **ML**: Model directory, retrain intervals, minimum samples
- **Application**: Flask port, debug mode

## 🔄 Status Transitions

The system automatically transitions tankers between states:

- **At Source** → **Loading** (15 minutes)
- **Loading** → **In Transit** (30 minutes)
- **In Transit** → **Reached Destination** (5 hours)
- **Reached Destination** → **Unloading** (45 minutes)
- **Unloading** → **At Source** (60 minutes)
- **Delayed** → **In Transit** (60 minutes)

Transitions are deterministic and time-based, ensuring realistic operational flow.

## 🤖 Machine Learning

### Models

1. **Arrival Time Prediction**
   - Predicts time until destination arrival
   - Uses Random Forest Regressor
   - Features: location, speed, distance, historical patterns

2. **Delay Probability**
   - Predicts likelihood of delays
   - Uses Random Forest Classifier
   - Features: status, location, time, historical delays

3. **Status Transition Prediction**
   - Predicts next status transition
   - Uses Random Forest Classifier
   - Features: current status, duration, location, patterns

### Training

- Models train automatically when sufficient data is available (default: 50 samples)
- Retraining occurs periodically (default: every hour)
- Models are stored in `./models/` directory
- Metadata is tracked in the database

## 📁 Project Structure

```
.
├── app.py                      # Main Flask application
├── api_endpoints.py            # REST API endpoints
├── config.py                   # Configuration management
├── data_generator.py           # Background data generation
├── ml_pipeline.py              # ML training and inference
├── ml_retrain_scheduler.py     # ML retraining scheduler
├── setup_database.py           # Database setup script
├── database_schema.sql         # PostgreSQL schema
├── requirements.txt            # Python dependencies
├── .env.example                # Environment variables template
├── index.html                  # Frontend chat interface
├── styles.css                  # CSS styling
└── README.md                   # This file
```

## 🐛 Troubleshooting

### Database Connection Errors
- Verify PostgreSQL is running: `pg_isready`
- Check credentials in `.env` file
- Ensure database exists: `psql -U postgres -l`

### Data Generator Not Running
- Check logs for errors
- Verify database connection
- Ensure background threads are started

### ML Models Not Training
- Check if sufficient data exists (minimum 50 samples)
- Verify `./models/` directory exists and is writable
- Check logs for training errors

### API Errors
- Verify all services are running
- Check database connection
- Review application logs

## 🔐 Security Notes

- **Never commit `.env` file** with real credentials
- Use environment variables for sensitive data
- Consider using connection pooling for production
- Implement authentication for production deployment

## 📈 Performance

- Database indexes optimized for time-series queries
- ML models use efficient Random Forest algorithms
- Background services run as daemon threads
- API responses are optimized with proper SQL queries

## 🚀 Production Deployment

For production deployment:

1. Set `FLASK_DEBUG=False` in `.env`
2. Use a production WSGI server (e.g., Gunicorn)
3. Configure PostgreSQL connection pooling
4. Set up proper logging
5. Use environment variables for all secrets
6. Consider using Redis for caching
7. Implement proper authentication/authorization

## 📝 License

This project is provided as-is for tanker data management purposes.

## 🤝 Contributing

This is an enterprise-like system designed for scalability and maintainability. When extending:

- Follow the modular architecture
- Add proper error handling and logging
- Update database schema migrations
- Document new features
- Add appropriate tests

---

**Built with**: Flask, PostgreSQL, scikit-learn, pandas, OpenRouter API
