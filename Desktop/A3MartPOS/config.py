# config.py
import os
from dotenv import load_dotenv

# Load environment variables from .env file located in the instance folder
# This is useful for keeping sensitive info out of version control
basedir = os.path.abspath(os.path.dirname(__file__))
instance_path = os.path.join(basedir, 'instance')
dotenv_path = os.path.join(instance_path, '.env')
load_dotenv(dotenv_path=dotenv_path)

class Config:
    """Base configuration class."""
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'you-will-never-guess' # CHANGE THIS! Stored in instance/.env
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    ITEMS_PER_PAGE = 15 # Example: How many items to show per page in tables
    LOW_STOCK_THRESHOLD = 10 # Threshold for low stock warnings
    BARCODE_PREFIX = "A3M" # Prefix for auto-generated barcodes
    BARCODE_START_NUMBER = 1 # Starting number for barcodes
    BARCODE_SYSTEM = 'code128' # Type of barcode to generate (e.g., 'ean13', 'code128')

    # Database configuration (using SQLite by default)
    # The actual URI is best kept in the instance/.env file for security
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(instance_path, 'a3mart.db')

    # Ensure the instance folder exists
    try:
        os.makedirs(instance_path)
    except OSError:
        pass # Already exists

    @staticmethod
    def init_app(app):
        pass

class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True

class ProductionConfig(Config):
    """Production configuration."""
    DEBUG = False
    # Add production-specific settings here (e.g., logging)
    # Ensure SECRET_KEY and DATABASE_URL are set securely via environment variables

# Dictionary to access config by name
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}