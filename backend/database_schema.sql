-- ============================================
-- Normalized PostgreSQL Schema for Tanker Management System
-- ============================================

-- Drop existing tables if needed (for clean setup)
DROP TABLE IF EXISTS tanker_history CASCADE;
DROP TABLE IF EXISTS tankers CASCADE;
DROP TABLE IF EXISTS depots CASCADE;
DROP TABLE IF EXISTS destinations CASCADE;
DROP TABLE IF EXISTS drivers CASCADE;
DROP TABLE IF EXISTS ml_predictions CASCADE;
DROP TABLE IF EXISTS ml_model_metadata CASCADE;

-- ============================================
-- Core Tables
-- ============================================

-- Depots table
CREATE TABLE depots (
    depot_id SERIAL PRIMARY KEY,
    depot_name VARCHAR(100) NOT NULL UNIQUE,
    location_lat DECIMAL(10, 6),
    location_lon DECIMAL(10, 6),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Destinations table
CREATE TABLE destinations (
    destination_id SERIAL PRIMARY KEY,
    destination_name VARCHAR(100) NOT NULL UNIQUE,
    location_lat DECIMAL(10, 6),
    location_lon DECIMAL(10, 6),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Drivers table
CREATE TABLE drivers (
    driver_id SERIAL PRIMARY KEY,
    driver_name VARCHAR(100) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Main tankers table (current state)
CREATE TABLE tankers (
    tanker_id VARCHAR(50) PRIMARY KEY,
    driver_id INTEGER REFERENCES drivers(driver_id),
    current_status VARCHAR(50) NOT NULL,
    current_location_lat DECIMAL(10, 6),
    current_location_lon DECIMAL(10, 6),
    source_depot_id INTEGER REFERENCES depots(depot_id),
    destination_id INTEGER REFERENCES destinations(destination_id),
    seal_status VARCHAR(20) NOT NULL,
    oil_volume_liters DECIMAL(10, 2),
    max_capacity_liters DECIMAL(10, 2) NOT NULL,
    last_update TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    trip_duration_hours DECIMAL(5, 2) DEFAULT 0,
    avg_speed_kmh DECIMAL(5, 2) DEFAULT 0,
    status_changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Historical records table (for time-series analysis)
CREATE TABLE tanker_history (
    history_id SERIAL PRIMARY KEY,
    tanker_id VARCHAR(50) NOT NULL,
    driver_id INTEGER REFERENCES drivers(driver_id),
    status VARCHAR(50) NOT NULL,
    location_lat DECIMAL(10, 6),
    location_lon DECIMAL(10, 6),
    source_depot_id INTEGER REFERENCES depots(depot_id),
    destination_id INTEGER REFERENCES destinations(destination_id),
    seal_status VARCHAR(20),
    oil_volume_liters DECIMAL(10, 2),
    max_capacity_liters DECIMAL(10, 2),
    trip_duration_hours DECIMAL(5, 2),
    avg_speed_kmh DECIMAL(5, 2),
    recorded_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ============================================
-- ML Tables
-- ============================================

-- ML Model Metadata
CREATE TABLE ml_model_metadata (
    model_id SERIAL PRIMARY KEY,
    model_type VARCHAR(50) NOT NULL,
    model_version VARCHAR(20) NOT NULL,
    training_date TIMESTAMP NOT NULL,
    accuracy_metrics JSONB,
    feature_columns TEXT[],
    model_path VARCHAR(255),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ML Predictions
CREATE TABLE ml_predictions (
    prediction_id SERIAL PRIMARY KEY,
    tanker_id VARCHAR(50) NOT NULL,
    model_id INTEGER REFERENCES ml_model_metadata(model_id),
    prediction_type VARCHAR(50) NOT NULL, -- 'arrival_time', 'delay_probability', 'status_transition'
    predicted_value DECIMAL(10, 2),
    confidence_score DECIMAL(5, 4),
    prediction_data JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================
-- Chat Intelligence Tables
-- ============================================

-- Chat History (stores all user interactions for learning)
CREATE TABLE chat_history (
    chat_id SERIAL PRIMARY KEY,
    user_message TEXT NOT NULL,
    bot_response TEXT NOT NULL,
    context VARCHAR(50) NOT NULL, -- 'dashboard', 'tanker-details', 'tanker-list', 'full_chat'
    tanker_id VARCHAR(50), -- NULL if not tanker-specific
    intent VARCHAR(50), -- 'tanker_status', 'eta_inquiry', 'delay_reason', 'trend_analysis', 'general_help'
    topic VARCHAR(50), -- 'specific_tanker', 'fleet_overview', 'historical_data', 'prediction_request'
    confidence_score DECIMAL(5, 4), -- Confidence in intent classification
    response_metadata JSONB, -- Additional metadata about the response
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Chat Feedback (explicit and implicit feedback)
CREATE TABLE chat_feedback (
    feedback_id SERIAL PRIMARY KEY,
    chat_id INTEGER REFERENCES chat_history(chat_id) ON DELETE CASCADE,
    feedback_type VARCHAR(20) NOT NULL, -- 'explicit_helpful', 'explicit_not_helpful', 'implicit_followup', 'implicit_clarification'
    feedback_value INTEGER, -- 1 for helpful/positive, 0 for not helpful/negative
    notes TEXT, -- Optional notes
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Chat Learning Patterns (learned patterns from history)
CREATE TABLE chat_learning_patterns (
    pattern_id SERIAL PRIMARY KEY,
    question_pattern TEXT NOT NULL, -- Normalized question pattern
    intent VARCHAR(50) NOT NULL,
    topic VARCHAR(50),
    suggested_response_template TEXT, -- Template for better responses
    usage_count INTEGER DEFAULT 1, -- How many times this pattern was used
    success_rate DECIMAL(5, 4), -- Success rate based on feedback
    last_used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================
-- Indexes for Performance
-- ============================================

-- Tankers table indexes
CREATE INDEX idx_tankers_status ON tankers(current_status);
CREATE INDEX idx_tankers_depot ON tankers(source_depot_id);
CREATE INDEX idx_tankers_destination ON tankers(destination_id);
CREATE INDEX idx_tankers_last_update ON tankers(last_update);
CREATE INDEX idx_tankers_status_changed ON tankers(status_changed_at);

-- History table indexes (critical for time-series queries)
CREATE INDEX idx_history_tanker_id ON tanker_history(tanker_id);
CREATE INDEX idx_history_recorded_at ON tanker_history(recorded_at);
CREATE INDEX idx_history_status ON tanker_history(status);
CREATE INDEX idx_history_tanker_time ON tanker_history(tanker_id, recorded_at DESC);

-- ML tables indexes
CREATE INDEX idx_predictions_tanker ON ml_predictions(tanker_id);
CREATE INDEX idx_predictions_type ON ml_predictions(prediction_type);
CREATE INDEX idx_predictions_created ON ml_predictions(created_at);

-- Chat Intelligence indexes
CREATE INDEX idx_chat_history_context ON chat_history(context);
CREATE INDEX idx_chat_history_tanker ON chat_history(tanker_id);
CREATE INDEX idx_chat_history_intent ON chat_history(intent);
CREATE INDEX idx_chat_history_created ON chat_history(created_at);
CREATE INDEX idx_chat_feedback_chat_id ON chat_feedback(chat_id);
CREATE INDEX idx_chat_learning_patterns_intent ON chat_learning_patterns(intent);
CREATE INDEX idx_chat_learning_patterns_usage ON chat_learning_patterns(usage_count DESC);

-- ============================================
-- Helper Functions
-- ============================================

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Trigger to auto-update updated_at
CREATE TRIGGER update_tankers_updated_at BEFORE UPDATE ON tankers
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================
-- Initial Data (Optional - for testing)
-- ============================================

-- Insert some common depots
INSERT INTO depots (depot_name, location_lat, location_lon) VALUES
    ('Islamabad', 33.6844, 73.0479),
    ('Lahore', 31.5204, 74.3587),
    ('Karachi', 24.8607, 67.0011),
    ('Rawalpindi', 33.5651, 73.0169)
ON CONFLICT (depot_name) DO NOTHING;

-- Insert realistic Pakistani oil, fuel, and energy companies as destinations
INSERT INTO destinations (destination_name, location_lat, location_lon) VALUES
    ('Pakistan State Oil (PSO)', 24.8607, 67.0011),  -- Karachi
    ('Shell Pakistan Limited (SPL)', 31.5204, 74.3587),  -- Lahore
    ('Total Parco Pakistan (TPP)', 33.6844, 73.0479),  -- Islamabad
    ('National Refinery Limited', 24.8607, 67.0011),  -- Karachi
    ('Attock Refinery Limited (ARL)', 33.5651, 73.0169),  -- Rawalpindi
    ('Hub Power Services Limited (HPSL)', 24.8607, 67.0011),  -- Karachi
    ('Cnergyico PK Limited', 24.8607, 67.0011),  -- Karachi
    ('Byco Petroleum Pakistan Limited', 24.8607, 67.0011),  -- Karachi
    ('Engro Energy', 24.8607, 67.0011),  -- Karachi
    ('Pak-Arab Refinery Limited (PARCO)', 31.4504, 73.1350)  -- Faisalabad
ON CONFLICT (destination_name) DO NOTHING;

