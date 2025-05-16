    #!/usr/bin/env bash
    # Exit on error
    set -o errexit

    echo "--- Starting Build Script (v3 - debug yaml) ---"
    echo "Current working directory: $(pwd)"
    echo "Listing files in project root:"
    ls -la

    echo "--- Node.js and npm Version ---"
    node -v || echo "Node not found or 'node -v' failed"
    npm -v || echo "npm not found or 'npm -v' failed"

    echo "--- Frontend Build (Tailwind CSS) ---"
    echo "Removing existing node_modules and package-lock.json (if any) for a clean install..."
    rm -rf node_modules
    rm -f package-lock.json

    echo "Running a clean npm install (npm ci or npm install)..."
    # npm ci is generally preferred if you have a package-lock.json
    # If you don't commit package-lock.json, npm install is fine.
    if [ -f "package-lock.json" ]; then
        npm ci
    else
        npm install
    fi
    echo "npm install/ci completed."

    echo "Attempting to explicitly install yaml (for diagnostics)..."
    npm install yaml --save-dev
    echo "Explicit yaml install attempted."

    echo "Listing contents of node_modules to check for yaml:"
    ls -la node_modules/ | grep yaml || echo "yaml directory not found in node_modules after explicit install"
    ls -la node_modules/yaml/dist/ || echo "node_modules/yaml/dist/ directory not found"


    echo "Running npm run build:css..."
    npm run build:css # This runs the script from your package.json
    echo "npm run build:css completed."

    echo "--- Checking for output.css ---"
    echo "Listing contents of ./app/static/css/dist/:"
    ls -la ./app/static/css/dist/ || echo "Directory ./app/static/css/dist/ not found or ls failed."
    if [ -f "./app/static/css/dist/output.css" ]; then
        echo "SUCCESS: ./app/static/css/dist/output.css exists."
    else
        echo "ERROR: ./app/static/css/dist/output.css DOES NOT EXIST after build."
    fi

    echo "--- Backend Setup ---"
    echo "Installing Python dependencies..."
    pip install -r requirements.txt
    echo "Python dependencies installed."

    export FLASK_APP=run.py
    echo "FLASK_APP set to run.py"

    echo "Running database migrations..."
    flask db upgrade
    echo "Database migrations completed."

    echo "--- Build Script Finished ---"
    