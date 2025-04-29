# app/customers/__init__.py
from flask import Blueprint

# Create the blueprint object
# 'customers' is the name of the blueprint
customers_bp = Blueprint('customers', __name__, template_folder='templates')

# Import the routes associated with this blueprint *after* creating the blueprint object
# This avoids circular imports
# We will create the routes.py file later
from . import routes