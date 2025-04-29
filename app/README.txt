# A3 Mart POS - Setup and Usage Guide

This document provides instructions on how to set up, run, and deploy the A3 Mart POS Flask application.

## Features

* Admin Login
* Dashboard (Today's Sales, Top Items, Low Stock - basic implementation)
* Manual + Barcode-based Billing Interface
* 58mm Thermal Receipt Text Generation (Integration via print modal)
* Automatic Barcode Generation (e.g., A3M00001)
* A4 PDF Barcode Sticker Sheet Generation
* Customer Database (Add/Edit/List/Search)
* Customer Selection during Billing
* Product Database (Add/Edit/List/Search)
* Purchase Entry (Updates Stock Quantity)
* A4 PDF Invoice Download
* MySQL Ready (Defaults to SQLite)

## Prerequisites

* Python 3.8+
* Git
* (Optional but Recommended) A virtual environment tool (`venv` is built into Python 3)
* (Optional) MySQL Server if switching from SQLite

## Setup Instructions (Local Development)

1.  **Clone the Repository (if applicable):**
    If you cloned this from GitHub:
    ```bash
    git clone [https://github.com/your-username/A3MartPOS.git](https://github.com/your-username/A3MartPOS.git)
    cd A3MartPOS
    ```
    If you built it locally, just navigate to your project folder:
    ```bash
    cd path/to/your/A3MartPOS
    ```

2.  **Create and Activate Virtual Environment:**
    (This isolates project dependencies)
    ```bash
    # Create venv (only once)
    python -m venv venv

    # Activate venv
    # Windows (cmd/powershell):
    .\venv\Scripts\activate
    # macOS/Linux (bash/zsh):
    source venv/bin/activate
    ```
    You should see `(venv)` at the beginning of your terminal prompt.

3.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Configure Environment Variables:**
    * Navigate to the `instance` folder. If it doesn't exist, create it: `mkdir instance`
    * Create a file named `.env` inside the `instance` folder.
    * Add the following content to `.env`, **generating a strong secret key**:
        ```text
        # instance/.env
        # Generate using: python -c 'import secrets; print(secrets.token_hex(24))'
        SECRET_KEY='YOUR_VERY_STRONG_RANDOM_SECRET_KEY_HERE'

        # Database URL (SQLite default)
        DATABASE_URL='sqlite:///a3mart.db'

        # --- Optional: MySQL Configuration ---
        # Uncomment and update if using MySQL
        # Ensure you have 'mysqlclient' installed (pip install mysqlclient)
        # DATABASE_URL='mysql+mysqlclient://DB_USER:DB_PASSWORD@DB_HOST/DB_NAME'

        # --- Optional: PostgreSQL Configuration ---
        # Uncomment and update if using PostgreSQL
        # Ensure you have 'psycopg2-binary' installed (pip install psycopg2-binary)
        # DATABASE_URL='postgresql+psycopg2://DB_USER:DB_PASSWORD@DB_HOST/DB_NAME'
        ```
    * **Important:** The `instance` folder and `.env` file are ignored by Git (via `.gitignore`) and should **not** be committed to version control.

5.  **Set Flask Environment Variable:**
    (Tells Flask how to find your app)
    ```bash
    # Windows (cmd):
    set FLASK_APP=run.py
    # Windows (PowerShell):
    $env:FLASK_APP = "run.py"
    # macOS/Linux:
    export FLASK_APP=run.py
    ```
    *(You might also set `FLASK_ENV=development` for debug mode)*

6.  **Initialize and Migrate Database:**
    (Creates the database and tables based on your models)
    ```bash
    # Initialize migrations directory (only once per project)
    flask db init

    # Generate the initial migration script
    flask db migrate -m "Initial database structure"

    # Apply the migration to create tables
    flask db upgrade
    ```
    This will create the `a3mart.db` file inside the `instance` folder (if using SQLite).

7.  **Create Initial Admin User:**
    ```bash
    flask create-admin your_admin_username your_admin_password
    ```
    (Replace with your desired admin login credentials)

## Running the Application

1.  **Ensure Virtual Environment is Active:** You should see `(venv)` in your prompt.
2.  **Ensure `FLASK_APP` is set.**
3.  **Run the Development Server:**
    ```bash
    flask run
    ```
    *(Alternatively: `python run.py`)*
4.  **Access the Application:** Open your web browser and go to `http://127.0.0.1:5000` (or the address shown in the terminal).
5.  **Login:** Use the admin credentials you created in the setup step.

## Deployment (Example: Render.com)

Render is a popular platform for deploying web applications like Flask.

1.  **Push to GitHub:** Ensure your latest code (excluding `instance`, `venv`, etc.) is pushed to your GitHub repository.
2.  **Create `build.sh`:** Create a file named `build.sh` in the root of your project with the following content:
    ```bash
    #!/usr/bin/env bash
    # Exit on error
    set -o errexit

    # Install dependencies
    pip install -r requirements.txt

    # Run database migrations
    flask db upgrade
    ```
    Make this file executable: `git update-index --chmod=+x build.sh` (Run this locally and commit/push).
3.  **Sign Up/Log In to Render:** Go to [https://render.com/](https://render.com/).
4.  **Create a New Web Service:**
    * Click "New" -> "Web Service".
    * Connect your GitHub account and select your `A3MartPOS` repository.
    * **Name:** Give your service a name (e.g., `a3mart-pos`).
    * **Region:** Choose a region close to you.
    * **Branch:** Select the branch to deploy (e.g., `main` or `master`).
    * **Root Directory:** Leave blank (unless your app is in a subfolder).
    * **Runtime:** Select `Python 3`.
    * **Build Command:** `./build.sh` (This will execute your build script).
    * **Start Command:** `gunicorn run:app` (Uses Gunicorn WSGI server for production).
    * **Instance Type:** Choose the free tier to start (can be scaled later).
5.  **Add Environment Variables:**
    * Go to the "Environment" tab for your new service.
    * Add **Secret Files**:
        * **Filename:** `instance/.env`
        * **Contents:** Paste the contents of your local `instance/.env` file (with your `SECRET_KEY` and `DATABASE_URL`). **Crucially, if using Render's PostgreSQL, update `DATABASE_URL` here to the internal connection string provided by Render for its database service.** If sticking with SQLite for simple deployment, the default path might work, but Render's filesystem is ephemeral, so data won't persist across deploys/restarts. **Using Render's PostgreSQL is highly recommended for persistent data.**
    * Add **Environment Variables**:
        * `PYTHON_VERSION`: Specify the Python version you used (e.g., `3.11.1`).
        * `FLASK_APP`: `run.py`
        * `FLASK_ENV`: `production` (Optional, disables debug mode)
6.  **Create Database (If using Render PostgreSQL):**
    * Go to "New" -> "PostgreSQL".
    * Create a database instance (free tier available).
    * Copy the "Internal Connection String" provided.
    * Paste this connection string as the value for the `DATABASE_URL` secret file content in your Web Service environment settings.
7.  **Deploy:** Click "Create Web Service". Render will pull your code, run `build.sh` (installing requirements and running migrations), and start the application using Gunicorn.
8.  **Access:** Once deployed, Render will provide a public URL (e.g., `https://a3mart-pos.onrender.com`). You'll need to run the `flask create-admin` command manually via Render's Shell tab initially if the database was newly created on Render.

## Notes

* **Thermal Printing:** The "Print Receipt" button generates text suitable for a thermal printer but requires separate software/hardware integration (e.g., a local print server, browser extension like QZ Tray, or specific printer APIs) to send the text directly to the printer. The current implementation uses the browser's basic print dialog.
* **Barcode Scanning:** The billing interface expects barcode data to appear in the product search input field. You'll need a USB or Bluetooth barcode scanner configured to act as a keyboard wedge (HID mode).
* **Security:** Always use strong passwords and keep your `SECRET_KEY` confidential. Review security best practices for Flask applications.
* **Data Backup:** Regularly back up your database, especially if using SQLite locally.