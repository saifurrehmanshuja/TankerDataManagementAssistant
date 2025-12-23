#!/bin/bash
# Build script for Render deployment
# Installs dependencies and initializes database

echo "==> Installing Python dependencies..."
cd backend && pip install -r requirements.txt

echo "==> Initializing database..."
python init_db.py

echo "==> Build complete!"

