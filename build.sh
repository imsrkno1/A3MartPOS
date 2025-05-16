#!/usr/bin/env bash
# Exit on error
set -o errexit

# ----- Frontend Build (Tailwind CSS) -----
echo ">>> Installing Node.js dependencies..."
npm install # This installs devDependencies like tailwindcss based on package.json

echo ">>> Building Tailwind CSS..."
npm run build:css # This runs the script from your package.json

# ----- Backend Setup -----
echo ">>> Installing Python dependencies..."
pip install -r requirements.txt

# Set FLASK_APP for migrations
export FLASK_APP=run.py

echo ">>> Running database migrations..."
flask db upgrade

echo "Build complete."