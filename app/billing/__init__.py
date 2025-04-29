# app/billing/__init__.py
from flask import Blueprint

# Create the blueprint object
# 'billing' is the name of the blueprint
billing_bp = Blueprint('billing', __name__, template_folder='templates')

# Import the routes associated with this blueprint *after* creating the blueprint object
# This avoids circular imports
# We will create the routes.py file later
from . import routes