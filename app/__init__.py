# app/__init__.py
import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from config import config # Import the config dictionary
from datetime import datetime # Import datetime

# Initialize extensions, but don't associate with an app yet
db = SQLAlchemy()
login_manager = LoginManager()
csrf = CSRFProtect()

# Configure Flask-Login
login_manager.session_protection = 'strong'
login_manager.login_view = 'auth.login'
login_manager.login_message = "Please log in to access this page."
login_manager.login_message_category = "info"

def create_app(config_name='default'):
    """
    Application factory function.
    Creates and configures the Flask application instance.
    """
    app = Flask(__name__, instance_relative_config=True)

    app.config.from_object(config[config_name])
    config[config_name].init_app(app)
    app.config.from_pyfile('config.py', silent=True)

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    # --- Register Blueprints ---
    # Import and register each blueprint
    from .auth import auth_bp as auth_blueprint
    app.register_blueprint(auth_blueprint, url_prefix='/auth')

    from .main import main_bp as main_blueprint
    app.register_blueprint(main_blueprint) # No prefix for main routes like dashboard

    from .billing import billing_bp as billing_blueprint
    app.register_blueprint(billing_blueprint, url_prefix='/billing')

    from .inventory import inventory_bp as inventory_blueprint
    app.register_blueprint(inventory_blueprint, url_prefix='/inventory')

    from .customers import customers_bp as customers_blueprint # Import as customers_blueprint
    # Use the correct variable name 'customers_blueprint' here:
    app.register_blueprint(customers_blueprint, url_prefix='/customers') # CORRECTED LINE

    # --- Context Processors ---
    @app.context_processor
    def inject_global_variables():
        """Inject variables automatically into the context of templates."""
        # Make app_name and datetime available globally in templates
        return dict(
            app_name=app.config.get('APP_NAME', "A3 Mart POS"), # Get app name from config or default
            now=datetime.utcnow # Make the datetime object available as 'now'
        )

    # --- Error Handling ---
    # (Keep existing error handlers or add them here)
    # from flask import render_template
    # @app.errorhandler(404)
    # def page_not_found(e):
    #     return render_template('404.html'), 404
    #
    # @app.errorhandler(500)
    # def internal_server_error(e):
    #     db.session.rollback() # Important for DB errors
    #     return render_template('500.html'), 500

    return app