# app/__init__.py
import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from config import config # Import the config dictionary

# Initialize extensions, but don't associate with an app yet
db = SQLAlchemy()
login_manager = LoginManager()
csrf = CSRFProtect()

# Configure Flask-Login
login_manager.session_protection = 'strong' # Protects against session hijacking
login_manager.login_view = 'auth.login' # The route name (blueprint.view_function) for the login page
login_manager.login_message = "Please log in to access this page."
login_manager.login_message_category = "info" # Bootstrap category for flash message

def create_app(config_name='default'):
    """
    Application factory function.
    Creates and configures the Flask application instance.
    """
    app = Flask(__name__, instance_relative_config=True) # Enable instance folder config

    # Load configuration from config.py and instance/config.py
    app.config.from_object(config[config_name])
    config[config_name].init_app(app)

    # Load configuration from instance/config.py if it exists
    # This allows overriding settings without modifying the main config files
    # Note: instance_relative_config=True is needed in Flask() constructor
    # Use silent=True to not raise an error if instance/config.py doesn't exist
    app.config.from_pyfile('config.py', silent=True)

    # Initialize extensions with the app instance
    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app) # Initialize CSRF protection

    # --- Register Blueprints ---
    # Blueprints help organize routes and views

    # Authentication Blueprint
    from .auth import auth_bp as auth_blueprint
    app.register_blueprint(auth_blueprint, url_prefix='/auth')

    # Main Blueprint (Dashboard, etc.)
    from .main import main_bp as main_blueprint
    app.register_blueprint(main_blueprint) # No prefix for main routes like dashboard

    # Billing Blueprint
    from .billing import billing_bp as billing_blueprint
    app.register_blueprint(billing_blueprint, url_prefix='/billing')

    # Inventory Blueprint (Products, Purchases)
    from .inventory import inventory_bp as inventory_blueprint
    app.register_blueprint(inventory_blueprint, url_prefix='/inventory')

    # Customers Blueprint
    from .customers import customers_bp as customers_blueprint
    app.register_blueprint(customers_blueprint, url_prefix='/customers')

    # --- Context Processors ---
    # Inject variables automatically into the context of templates
    @app.context_processor
    def inject_global_variables():
        # Example: Make app name available in all templates
        return dict(app_name="A3 Mart POS")

    # --- Error Handling ---
    # You can define custom error pages here (e.g., for 404, 500)
    # from flask import render_template
    # @app.errorhandler(404)
    # def page_not_found(e):
    #     return render_template('404.html'), 404
    #
    # @app.errorhandler(500)
    # def internal_server_error(e):
    #     # Important: rollback the session in case of DB errors during the request
    #     db.session.rollback()
    #     return render_template('500.html'), 500

    # --- Request Hooks ---
    # @app.before_request
    # def before_request_func():
    #     pass # Code to run before each request

    # @app.after_request
    # def after_request_func(response):
    #     # Code to run after each request, before sending response
    #     return response

    # @app.teardown_appcontext
    # def teardown_db(exception):
    #     # Code to run after request, even if exceptions occur
    #     pass # Can be used to close resources, etc.

    # Print statements for debugging configuration loading (optional)
    # print(f"--- App Configuration ---")
    # print(f"Instance Path: {app.instance_path}")
    # print(f"Database URI: {app.config.get('SQLALCHEMY_DATABASE_URI')}")
    # print(f"Secret Key Set: {'Yes' if app.config.get('SECRET_KEY') != 'you-will-never-guess' else 'No (Using default!)'}")
    # print(f"Debug Mode: {app.config.get('DEBUG')}")
    # print(f"-------------------------")

    return app