# app/main/routes.py
from flask import render_template, redirect, url_for, flash
from flask_login import login_required, current_user

from . import main_bp # Import the blueprint instance from app/main/__init__.py
from ..models import Sale, Product, SaleItem # Import models needed for dashboard data
from .. import db # Import the database instance
from datetime import datetime, date, timedelta

@main_bp.route('/') # Route for the homepage
@main_bp.route('/dashboard') # Route for the dashboard
@login_required # User must be logged in to access the dashboard
def dashboard():
    """Renders the main dashboard page."""

    # --- Placeholder Data Fetching ---
    # In a real application, you'd query the database here
    # For example:

    # Today's Sales Calculation
    today_start = datetime.combine(date.today(), datetime.min.time())
    today_end = datetime.combine(date.today(), datetime.max.time())
    todays_sales_query = db.session.query(db.func.sum(Sale.final_amount)).filter(
        Sale.sale_timestamp >= today_start,
        Sale.sale_timestamp <= today_end
    )
    todays_sales_total = todays_sales_query.scalar() or 0.0 # Use scalar() to get single value, default to 0.0 if None

    # Top Selling Items (Example: Top 5 by quantity today)
    top_items_query = db.session.query(
        Product.name,
        db.func.sum(SaleItem.quantity).label('total_quantity')
    ).join(SaleItem, SaleItem.product_id == Product.id)\
     .join(Sale, Sale.id == SaleItem.sale_id)\
     .filter(Sale.sale_timestamp >= today_start, Sale.sale_timestamp <= today_end)\
     .group_by(Product.name)\
     .order_by(db.desc('total_quantity'))\
     .limit(5)
    top_items = top_items_query.all() # Returns list of tuples (name, total_quantity)

    # Low Stock Items (Example: Items below or at threshold)
    low_stock_items = Product.query.filter(
        Product.stock_quantity <= Product.low_stock_threshold,
        Product.is_active == True # Only consider active products
    ).order_by(Product.stock_quantity.asc()).limit(10).all() # Get up to 10 low stock items

    # --- Pass data to the template ---
    dashboard_data = {
        'todays_sales': todays_sales_total,
        'top_items': top_items,
        'low_stock_items': low_stock_items
    }

    return render_template('main/dashboard.html', title='Dashboard', data=dashboard_data)

# Add other main routes here if needed (e.g., profile page)