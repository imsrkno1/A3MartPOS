# app/auth/__init__.py
from flask import Blueprint

# Create the blueprint object
# 'auth' is the name of the blueprint
# __name__ helps Flask locate the blueprint's root path
# template_folder='templates' tells Flask to look for templates in an 'auth/templates' subfolder (optional)
auth_bp = Blueprint('auth', __name__, template_folder='templates')

# Import the routes associated with this blueprint *after* creating the blueprint object
# This avoids circular imports
# We will create the routes.py file later
from . import routes