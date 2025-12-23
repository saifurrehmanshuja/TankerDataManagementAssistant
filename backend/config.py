"""
Configuration file for Tanker Management System
Uses environment variables with sensible defaults
"""
import os

# Try to load environment variables from .env file if it exists
try:
    from dotenv import load_dotenv
    from pathlib import Path
    # Load .env from the backend directory (where this file is located)
    env_path = Path(__file__).parent / '.env'
    load_dotenv(dotenv_path=env_path)
except ImportError:
    # python-dotenv not installed, continue without it
    # Environment variables can still be set manually
    pass

# Database Configuration
POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "root")
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
DATABASE_NAME = os.getenv("DATABASE_NAME", "tankerdb")

# OpenRouter API Configuration
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
if not OPENROUTER_API_KEY:
    raise ValueError(
        "OPENROUTER_API_KEY environment variable is required.\n"
        "Please create a .env file in the backend directory with:\n"
        "OPENROUTER_API_KEY=your_api_key_here\n\n"
        "Or set it as an environment variable before running the app."
    )
OPENROUTER_URL = os.getenv(
    "OPENROUTER_URL",
    "https://openrouter.ai/api/v1/chat/completions"
)

# Data Generator Configuration
DATA_GENERATION_INTERVAL = int(os.getenv("DATA_GENERATION_INTERVAL", "30"))  # seconds
STATUS_TRANSITION_INTERVAL = int(os.getenv("STATUS_TRANSITION_INTERVAL", "300"))  # 5 minutes in seconds

# ML Configuration
ML_MODEL_DIR = os.getenv("ML_MODEL_DIR", "./models")
ML_RETRAIN_INTERVAL = int(os.getenv("ML_RETRAIN_INTERVAL", "3600"))  # 1 hour in seconds
ML_MIN_SAMPLES_FOR_TRAINING = int(os.getenv("ML_MIN_SAMPLES_FOR_TRAINING", "50"))

# Application Configuration (for Render deployment)
# PORT is set by Render automatically

