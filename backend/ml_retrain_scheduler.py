"""
Continuous ML Model Retraining Scheduler
Runs periodic retraining of ML models as new data accumulates
"""
import time
import threading
import logging
from config import ML_RETRAIN_INTERVAL
from ml_pipeline import get_ml_pipeline

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MLRetrainScheduler:
    """Schedules periodic ML model retraining"""
    
    def __init__(self):
        self.running = False
        self.thread = None
        self.ml_pipeline = get_ml_pipeline()
    
    def retrain_worker(self):
        """Background worker for periodic retraining"""
        # Wait initially to allow data to accumulate
        from config import DATA_GENERATION_INTERVAL, ML_MIN_SAMPLES_FOR_TRAINING
        initial_wait = max(120, DATA_GENERATION_INTERVAL * (ML_MIN_SAMPLES_FOR_TRAINING // 2))
        logger.info(f"ML retrain scheduler: Waiting {initial_wait} seconds before first training attempt...")
        time.sleep(initial_wait)
        
        while self.running:
            try:
                logger.info("Starting scheduled ML model retraining...")
                success = self.ml_pipeline.train_all_models()
                if success:
                    logger.info(f"✅ ML retraining complete. Next retrain in {ML_RETRAIN_INTERVAL} seconds")
                else:
                    logger.debug("⏳ ML retraining skipped (not enough data yet). Will retry in next cycle.")
                time.sleep(ML_RETRAIN_INTERVAL)
            except Exception as e:
                logger.error(f"Error in ML retraining: {e}")
                time.sleep(3600)  # Wait an hour before retrying on error
    
    def start(self):
        """Start the retraining scheduler"""
        if self.running:
            logger.warning("ML retrain scheduler is already running")
            return
        
        self.running = True
        self.thread = threading.Thread(target=self.retrain_worker, daemon=True)
        self.thread.start()
        logger.info("ML retrain scheduler started")
    
    def stop(self):
        """Stop the retraining scheduler"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        logger.info("ML retrain scheduler stopped")


# Global instance
_retrain_scheduler = None

def get_retrain_scheduler():
    """Get or create the global retrain scheduler instance"""
    global _retrain_scheduler
    if _retrain_scheduler is None:
        _retrain_scheduler = MLRetrainScheduler()
    return _retrain_scheduler

