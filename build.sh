#!/usr/bin/env bash
# Exit on error
set -o errexit

# Install dependencies
pip install -r requirements.txt

# Set FLASK_APP for migrations (Render might not pick it up automatically here)
export FLASK_APP=run.py

# Run database migrations
flask db upgrade