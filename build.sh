#!/usr/bin/env bash
# Exit on error
set -o errexit

echo "--- Starting Build Script ---"
echo "Current working directory: $(pwd)"
echo "Listing files in project root:"
ls -la

echo "--- Node.js and npm Version ---"
node -v || echo "Node not found or 'node -v' failed"
npm -v || echo "npm not found or 'npm -v' failed"

echo "--- Frontend Build (Tailwind CSS) ---"
echo "Running npm install..."
npm install
echo "npm install completed."

echo "Running npm run build:css..."
npm run build:css # This runs the script from your package.json
echo "npm run build:css completed."

echo "--- Checking for output.css ---"
echo "Listing contents of ./app/static/css/dist/:"
ls -la ./app/static/css/dist/ || echo "Directory ./app/static/css/dist/ not found or ls failed."
echo "Checking if output.css exists specifically:"
if [ -f "./app/static/css/dist/output.css" ]; then
    echo "SUCCESS: ./app/static/css/dist/output.css exists."
else
    echo "ERROR: ./app/static/css/dist/output.css DOES NOT EXIST after build."
fi
echo "Listing contents of ./app/static/ (for context):"
ls -la ./app/static/
echo "Listing contents of ./app/static/css/ (for context):"
ls -la ./app/static/css/

echo "--- Backend Setup ---"
echo "Installing Python dependencies..."
pip install -r requirements.txt
echo "Python dependencies installed."

# Set FLASK_APP for migrations
export FLASK_APP=run.py
echo "FLASK_APP set to run.py"

echo "Running database migrations..."
flask db upgrade
echo "Database migrations completed."

echo "--- Build Script Finished ---"