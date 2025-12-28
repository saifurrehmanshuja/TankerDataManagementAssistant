"""
Continuous Machine Learning Pipeline
Learns patterns from tanker data and provides predictions
"""
import psycopg2
from psycopg2 import extras
import numpy as np
import pandas as pd
import pickle
import os
import logging
import json
from datetime import datetime, timedelta

# Configure logging first
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Try to import sklearn, but make it optional
try:
    from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier
    from sklearn.model_selection import train_test_split
    from sklearn.preprocessing import StandardScaler
    from sklearn.metrics import mean_absolute_error, accuracy_score, classification_report
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    logger.warning("scikit-learn not installed. ML features will be disabled. Install with: pip install scikit-learn")

from config import (
    POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_HOST,
    POSTGRES_PORT, DATABASE_NAME, ML_MODEL_DIR, ML_MIN_SAMPLES_FOR_TRAINING
)


class TankerMLPipeline:
    """Machine Learning pipeline for tanker operations"""
    
    def __init__(self):
        self.model_dir = ML_MODEL_DIR
        os.makedirs(self.model_dir, exist_ok=True)
        
        # Model types
        self.models = {
            "arrival_time": None,
            "delay_probability": None,
            "status_transition": None
        }
        
        self.scalers = {}
        self.model_metadata = {}
    
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
    
    def load_training_data(self, min_samples=ML_MIN_SAMPLES_FOR_TRAINING):
        """Load historical data for training"""
        conn = self.get_db_connection()
        if not conn:
            return None
        
        try:
            # Load historical data with features
            query = """
                SELECT 
                    h.tanker_id,
                    h.status,
                    h.location_lat,
                    h.location_lon,
                    h.oil_volume_liters,
                    h.max_capacity_liters,
                    h.trip_duration_hours,
                    h.avg_speed_kmh,
                    h.recorded_at,
                    d.depot_name as source_depot,
                    dest.destination_name as destination,
                    dr.driver_name,
                    -- Calculate distance (simplified)
                    ABS(h.location_lat - COALESCE(dest.location_lat, h.location_lat)) +
                    ABS(h.location_lon - COALESCE(dest.location_lon, h.location_lon)) as distance_to_dest,
                    -- Time features
                    EXTRACT(HOUR FROM h.recorded_at) as hour_of_day,
                    EXTRACT(DOW FROM h.recorded_at) as day_of_week,
                    -- Lag features (previous status duration)
                    LAG(h.recorded_at) OVER (PARTITION BY h.tanker_id ORDER BY h.recorded_at) as prev_recorded_at
                FROM tanker_history h
                LEFT JOIN depots d ON h.source_depot_id = d.depot_id
                LEFT JOIN destinations dest ON h.destination_id = dest.destination_id
                LEFT JOIN drivers dr ON h.driver_id = dr.driver_id
                WHERE h.recorded_at >= CURRENT_TIMESTAMP - INTERVAL '30 days'
                ORDER BY h.tanker_id, h.recorded_at
            """
            
            df = pd.read_sql_query(query, conn)
            
            if len(df) < min_samples:
                logger.debug(f"Not enough training samples yet: {len(df)} < {min_samples}. Need {min_samples - len(df)} more samples.")
                return None
            
            # Calculate time differences
            df['prev_recorded_at'] = pd.to_datetime(df['prev_recorded_at'])
            df['recorded_at'] = pd.to_datetime(df['recorded_at'])
            df['time_since_last'] = (df['recorded_at'] - df['prev_recorded_at']).dt.total_seconds() / 3600
            df['time_since_last'] = df['time_since_last'].fillna(0)
            
            # Calculate status duration (for transitions)
            df['status_duration'] = df.groupby(['tanker_id', 'status'])['time_since_last'].cumsum()
            
            conn.close()
            return df
            
        except Exception as e:
            logger.error(f"Error loading training data: {e}")
            if conn:
                conn.close()
            return None
    
    def prepare_features(self, df):
        """Prepare features for ML models"""
        # Encode categorical variables
        status_encoded = pd.get_dummies(df['status'], prefix='status')
        depot_encoded = pd.get_dummies(df['source_depot'], prefix='depot', dummy_na=True)
        dest_encoded = pd.get_dummies(df['destination'], prefix='dest', dummy_na=True)
        
        # Numerical features
        numerical_features = [
            'location_lat', 'location_lon',
            'oil_volume_liters', 'max_capacity_liters',
            'trip_duration_hours', 'avg_speed_kmh',
            'distance_to_dest', 'hour_of_day', 'day_of_week',
            'time_since_last', 'status_duration'
        ]
        
        # Combine all features
        features = pd.concat([
            df[numerical_features].fillna(0),
            status_encoded,
            depot_encoded,
            dest_encoded
        ], axis=1)
        
        return features
    
    def train_arrival_time_model(self, df):
        """Train model to predict arrival time"""
        if not SKLEARN_AVAILABLE:
            logger.error("Cannot train model: scikit-learn not installed")
            return False
        try:
            # Filter for in-transit tankers
            transit_df = df[df['status'] == 'In Transit'].copy()
            
            if len(transit_df) < ML_MIN_SAMPLES_FOR_TRAINING:
                logger.warning("Not enough in-transit samples for arrival time model")
                return False
            
            # Target: time until reaching destination (simplified)
            # For now, predict trip_duration_hours based on distance and speed
            transit_df['target'] = transit_df['trip_duration_hours']
            
            # Prepare features
            X = self.prepare_features(transit_df)
            y = transit_df['target'].fillna(0)
            
            # Remove rows with invalid targets
            valid_mask = (y > 0) & (y < 100)  # Reasonable bounds
            X = X[valid_mask]
            y = y[valid_mask]
            
            if len(X) < ML_MIN_SAMPLES_FOR_TRAINING:
                logger.warning("Not enough valid samples for arrival time model")
                return False
            
            # Split data
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=0.2, random_state=42
            )
            
            # Scale features
            scaler = StandardScaler()
            X_train_scaled = scaler.fit_transform(X_train)
            X_test_scaled = scaler.transform(X_test)
            
            # Train model
            model = RandomForestRegressor(n_estimators=50, max_depth=10, random_state=42)
            model.fit(X_train_scaled, y_train)
            
            # Evaluate
            y_pred = model.predict(X_test_scaled)
            mae = mean_absolute_error(y_test, y_pred)
            
            logger.info(f"Arrival time model trained. MAE: {mae:.2f} hours")
            
            # Save model
            model_path = os.path.join(self.model_dir, "arrival_time_model.pkl")
            scaler_path = os.path.join(self.model_dir, "arrival_time_scaler.pkl")
            
            with open(model_path, 'wb') as f:
                pickle.dump(model, f)
            with open(scaler_path, 'wb') as f:
                pickle.dump(scaler, f)
            
            self.models["arrival_time"] = model
            self.scalers["arrival_time"] = scaler
            
            # Save metadata to database
            self.save_model_metadata("arrival_time", mae, list(X.columns))
            
            return True
            
        except Exception as e:
            logger.error(f"Error training arrival time model: {e}")
            return False
    
    def train_delay_probability_model(self, df):
        """Train model to predict delay probability"""
        if not SKLEARN_AVAILABLE:
            logger.error("Cannot train model: scikit-learn not installed")
            return False
        try:
            # Create delay label (1 if status is "Delayed", 0 otherwise)
            df['is_delayed'] = (df['status'] == 'Delayed').astype(int)
            
            # Prepare features
            X = self.prepare_features(df)
            y = df['is_delayed']
            
            if len(X) < ML_MIN_SAMPLES_FOR_TRAINING:
                logger.warning("Not enough samples for delay probability model")
                return False
            
            # Split data
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=0.2, random_state=42, stratify=y
            )
            
            # Scale features
            scaler = StandardScaler()
            X_train_scaled = scaler.fit_transform(X_train)
            X_test_scaled = scaler.transform(X_test)
            
            # Train model
            model = RandomForestClassifier(n_estimators=50, max_depth=10, random_state=42)
            model.fit(X_train_scaled, y_train)
            
            # Evaluate
            y_pred = model.predict(X_test_scaled)
            accuracy = accuracy_score(y_test, y_pred)
            
            logger.info(f"Delay probability model trained. Accuracy: {accuracy:.2%}")
            
            # Save model
            model_path = os.path.join(self.model_dir, "delay_probability_model.pkl")
            scaler_path = os.path.join(self.model_dir, "delay_probability_scaler.pkl")
            
            with open(model_path, 'wb') as f:
                pickle.dump(model, f)
            with open(scaler_path, 'wb') as f:
                pickle.dump(scaler, f)
            
            self.models["delay_probability"] = model
            self.scalers["delay_probability"] = scaler
            
            # Save metadata
            self.save_model_metadata("delay_probability", accuracy, list(X.columns))
            
            return True
            
        except Exception as e:
            logger.error(f"Error training delay probability model: {e}")
            return False
    
    def train_status_transition_model(self, df):
        """Train model to predict next status transition"""
        if not SKLEARN_AVAILABLE:
            logger.error("Cannot train model: scikit-learn not installed")
            return False
        try:
            # Create next status target
            df = df.sort_values(['tanker_id', 'recorded_at'])
            df['next_status'] = df.groupby('tanker_id')['status'].shift(-1)
            df = df[df['next_status'].notna()]
            
            if len(df) < ML_MIN_SAMPLES_FOR_TRAINING:
                logger.warning("Not enough samples for status transition model")
                return False
            
            # Prepare features
            X = self.prepare_features(df)
            y = df['next_status']
            
            # Split data
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=0.2, random_state=42
            )
            
            # Scale features
            scaler = StandardScaler()
            X_train_scaled = scaler.fit_transform(X_train)
            X_test_scaled = scaler.transform(X_test)
            
            # Train model
            model = RandomForestClassifier(n_estimators=50, max_depth=10, random_state=42)
            model.fit(X_train_scaled, y_train)
            
            # Evaluate
            y_pred = model.predict(X_test_scaled)
            accuracy = accuracy_score(y_test, y_pred)
            
            logger.info(f"Status transition model trained. Accuracy: {accuracy:.2%}")
            
            # Save model
            model_path = os.path.join(self.model_dir, "status_transition_model.pkl")
            scaler_path = os.path.join(self.model_dir, "status_transition_scaler.pkl")
            
            with open(model_path, 'wb') as f:
                pickle.dump(model, f)
            with open(scaler_path, 'wb') as f:
                pickle.dump(scaler, f)
            
            self.models["status_transition"] = model
            self.scalers["status_transition"] = scaler
            
            # Save metadata
            self.save_model_metadata("status_transition", accuracy, list(X.columns))
            
            return True
            
        except Exception as e:
            logger.error(f"Error training status transition model: {e}")
            return False
    
    def save_model_metadata(self, model_type, metric_value, feature_columns):
        """Save model metadata to database"""
        conn = self.get_db_connection()
        if not conn:
            return
        
        try:
            cursor = conn.cursor()
            
            # Deactivate old models of this type
            cursor.execute("""
                UPDATE ml_model_metadata 
                SET is_active = FALSE 
                WHERE model_type = %s
            """, (model_type,))
            
            # Insert new model metadata
            model_version = datetime.now().strftime("%Y%m%d_%H%M%S")
            model_path = os.path.join(self.model_dir, f"{model_type}_model.pkl")
            
            accuracy_metrics = {
                "metric_value": float(metric_value),
                "metric_type": "mae" if model_type == "arrival_time" else "accuracy"
            }
            
            cursor.execute("""
                INSERT INTO ml_model_metadata (
                    model_type, model_version, training_date,
                    accuracy_metrics, feature_columns, model_path, is_active
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                model_type, model_version, datetime.now(),
                json.dumps(accuracy_metrics),
                feature_columns, model_path, True
            ))
            
            conn.commit()
            cursor.close()
            
        except Exception as e:
            logger.error(f"Error saving model metadata: {e}")
            conn.rollback()
        finally:
            conn.close()
    
    def load_models(self):
        """Load trained models from disk"""
        try:
            for model_type in self.models.keys():
                model_path = os.path.join(self.model_dir, f"{model_type}_model.pkl")
                scaler_path = os.path.join(self.model_dir, f"{model_type}_scaler.pkl")
                
                if os.path.exists(model_path) and os.path.exists(scaler_path):
                    with open(model_path, 'rb') as f:
                        self.models[model_type] = pickle.load(f)
                    with open(scaler_path, 'rb') as f:
                        self.scalers[model_type] = pickle.load(f)
                    logger.info(f"Loaded {model_type} model")
        except Exception as e:
            logger.error(f"Error loading models: {e}")
    
    def predict_arrival_time(self, tanker_id):
        """Predict arrival time for a tanker"""
        if not SKLEARN_AVAILABLE:
            logger.warning("ML predictions unavailable: scikit-learn not installed")
            return None
        
        # Lazy-load models only when needed
        if self.models["arrival_time"] is None:
            try:
                self.load_models()
            except Exception as e:
                logger.warning(f"Could not load ML models: {e}")
                return None
        
        if self.models["arrival_time"] is None:
            return None
        
        conn = self.get_db_connection()
        if not conn:
            return None
        
        try:
            # Get current tanker data
            query = """
                SELECT 
                    t.tanker_id, t.current_status,
                    t.current_location_lat, t.current_location_lon,
                    t.oil_volume_liters, t.max_capacity_liters,
                    t.trip_duration_hours, t.avg_speed_kmh,
                    d.depot_name as source_depot,
                    dest.destination_name as destination,
                    dest.location_lat as dest_lat,
                    dest.location_lon as dest_lon,
                    dr.driver_name
                FROM tankers t
                LEFT JOIN depots d ON t.source_depot_id = d.depot_id
                LEFT JOIN destinations dest ON t.destination_id = dest.destination_id
                LEFT JOIN drivers dr ON t.driver_id = dr.driver_id
                WHERE LOWER(t.tanker_id) = LOWER(%s)
            """
            
            df = pd.read_sql_query(query, conn, params=(tanker_id,))
            
            if len(df) == 0:
                return None
            
            # Calculate features
            row = df.iloc[0]
            distance = abs(row['current_location_lat'] - row['dest_lat']) + \
                      abs(row['current_location_lon'] - row['dest_lon'])
            
            # Prepare features (simplified - would need full feature engineering)
            features = self.prepare_features(df)
            
            if len(features) == 0:
                return None
            
            # Predict
            scaler = self.scalers["arrival_time"]
            model = self.models["arrival_time"]
            
            features_scaled = scaler.transform(features)
            prediction = model.predict(features_scaled)[0]
            
            return max(0, prediction)  # Ensure non-negative
            
        except Exception as e:
            logger.error(f"Error predicting arrival time: {e}")
            return None
        finally:
            conn.close()
    
    def predict_delay_probability(self, tanker_id):
        """Predict delay probability for a tanker"""
        if not SKLEARN_AVAILABLE:
            logger.warning("ML predictions unavailable: scikit-learn not installed")
            return None
        
        # Lazy-load models only when needed
        if self.models["delay_probability"] is None:
            try:
                self.load_models()
            except Exception as e:
                logger.warning(f"Could not load ML models: {e}")
                return None
        
        if self.models["delay_probability"] is None:
            return None
        
        conn = self.get_db_connection()
        if not conn:
            return None
        
        try:
            # Get current tanker data
            query = """
                SELECT 
                    t.tanker_id, t.current_status,
                    t.current_location_lat, t.current_location_lon,
                    t.oil_volume_liters, t.max_capacity_liters,
                    t.trip_duration_hours, t.avg_speed_kmh,
                    d.depot_name as source_depot,
                    dest.destination_name as destination,
                    dr.driver_name
                FROM tankers t
                LEFT JOIN depots d ON t.source_depot_id = d.depot_id
                LEFT JOIN destinations dest ON t.destination_id = dest.destination_id
                LEFT JOIN drivers dr ON t.driver_id = dr.driver_id
                WHERE LOWER(t.tanker_id) = LOWER(%s)
            """
            
            df = pd.read_sql_query(query, conn, params=(tanker_id,))
            
            if len(df) == 0:
                return None
            
            # Prepare features
            features = self.prepare_features(df)
            
            if len(features) == 0:
                return None
            
            # Predict
            scaler = self.scalers["delay_probability"]
            model = self.models["delay_probability"]
            
            features_scaled = scaler.transform(features)
            probability = model.predict_proba(features_scaled)[0][1]  # Probability of delay
            
            return float(probability)
            
        except Exception as e:
            logger.error(f"Error predicting delay probability: {e}")
            return None
        finally:
            conn.close()
    
    def train_all_models(self):
        """Train all ML models"""
        logger.info("Starting ML model training...")
        
        df = self.load_training_data()
        if df is None:
            logger.info("No training data available yet. This is normal when the system first starts. Training will be retried automatically as data accumulates.")
            return False
        
        results = {
            "arrival_time": self.train_arrival_time_model(df),
            "delay_probability": self.train_delay_probability_model(df),
            "status_transition": self.train_status_transition_model(df)
        }
        
        logger.info(f"Training complete. Results: {results}")
        return any(results.values())


# Global instance
_ml_pipeline = None

def get_ml_pipeline():
    """Get or create the global ML pipeline instance"""
    global _ml_pipeline
    if _ml_pipeline is None:
        _ml_pipeline = TankerMLPipeline()
        _ml_pipeline.load_models()
    return _ml_pipeline

