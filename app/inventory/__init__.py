# app/inventory/__init__.py
from flask import Blueprint

# Create the blueprint object
# 'inventory' is the name of the blueprint
inventory_bp = Blueprint('inventory', __name__, template_folder='templates')

# Import the routes associated with this blueprint *after* creating the blueprint object
# This avoids circular imports
# We will create the routes.py file later
from . import routes