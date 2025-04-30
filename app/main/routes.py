# app/main/routes.py
from flask import render_template, redirect, url_for, flash, request, current_app # Added request, current_app
from flask_login import login_required, current_user
from sqlalchemy import func, extract # Import func for aggregate functions, extract for date parts
from collections import defaultdict # For grouping monthly sales

from . import main_bp # Import the blueprint instance
from ..models import Sale, Product, SaleItem, Customer # Import models needed for dashboard/reports
from .. import db # Import the database instance
from datetime import datetime, date, timedelta

@main_bp.route('/') # Route for the homepage
@main_bp.route('/dashboard') # Route for the dashboard
@login_required # User must be logged in to access the dashboard
def dashboard():
    """Renders the main dashboard page."""

    # --- Data Fetching for Dashboard ---
    today_start = datetime.combine(date.today(), datetime.min.time())
    today_end = datetime.combine(date.today(), datetime.max.time())

    # Today's Sales Calculation
    todays_sales_query = db.session.query(
        func.sum(Sale.final_amount).label('total_sales'),
        func.count(Sale.id).label('order_count') # Count number of sales
    ).filter(
        Sale.sale_timestamp >= today_start,
        Sale.sale_timestamp <= today_end
    )
    todays_summary = todays_sales_query.first() # Returns a Row object or None
    todays_sales_total = todays_summary.total_sales or 0.0
    todays_order_count = todays_summary.order_count or 0

    # Top Selling Items (Example: Top 5 by quantity today)
    top_items_query = db.session.query(
        Product.name,
        func.sum(SaleItem.quantity).label('total_quantity')
    ).join(SaleItem, SaleItem.product_id == Product.id)\
     .join(Sale, Sale.id == SaleItem.sale_id)\
     .filter(Sale.sale_timestamp >= today_start, Sale.sale_timestamp <= today_end)\
     .group_by(Product.name)\
     .order_by(db.desc('total_quantity'))\
     .limit(5)
    top_items = top_items_query.all()

    # Low Stock Items
    low_stock_items = Product.query.filter(
        Product.stock_quantity <= Product.low_stock_threshold,
        Product.is_active == True
    ).order_by(Product.stock_quantity.asc()).limit(10).all()

    # New Customers Today (Example)
    new_customers_today = Customer.query.filter(
        Customer.created_at >= today_start,
        Customer.created_at <= today_end
    ).count()

    # --- Pass data to the template ---
    dashboard_data = {
        'todays_sales': todays_sales_total,
        'todays_orders': todays_order_count, # Pass order count
        'new_customers': new_customers_today, # Pass new customer count
        'top_items': top_items,
        'low_stock_items': low_stock_items
    }

    return render_template('main/dashboard.html', title='Dashboard', data=dashboard_data)


# --- Sales Report by Date Range Route ---
@main_bp.route('/reports/sales_by_date') # Renamed route for clarity
@login_required
def sales_by_date_report():
    """Displays a sales report for a specific date range (defaults to today)."""
    # Get dates from query parameters, default to today
    today_iso = date.today().isoformat()
    start_date_str = request.args.get('start_date', today_iso)
    end_date_str = request.args.get('end_date', today_iso)

    try:
        start_date = date.fromisoformat(start_date_str)
        end_date = date.fromisoformat(end_date_str)
        # Ensure start_date is not after end_date
        if start_date > end_date:
            flash('Start date cannot be after end date. Showing report for selected start date only.', 'warning')
            end_date = start_date
            end_date_str = start_date_str
    except ValueError:
        flash('Invalid date format provided. Showing report for today.', 'warning')
        start_date = date.today()
        end_date = date.today()
        start_date_str = end_date_str = start_date.isoformat()

    # Calculate start and end timestamps for the selected date range
    start_dt = datetime.combine(start_date, datetime.min.time())
    end_dt = datetime.combine(end_date, datetime.max.time()) # Include the whole end day

    # Query sales for the selected date range
    sales_in_range = Sale.query.options(
        db.joinedload(Sale.customer),
        db.joinedload(Sale.user)
    ).filter(
        Sale.sale_timestamp >= start_dt,
        Sale.sale_timestamp <= end_dt
    ).order_by(Sale.sale_timestamp.asc()).all()

    # Calculate summary statistics
    total_sales = sum(s.final_amount for s in sales_in_range)
    total_discount = sum(s.discount_total for s in sales_in_range)
    number_of_sales = len(sales_in_range)

    # Prepare data for the template
    report_data = {
        'start_date': start_date,
        'end_date': end_date,
        'sales': sales_in_range,
        'total_sales': total_sales,
        'total_discount': total_discount,
        'number_of_sales': number_of_sales
    }

    # Use the same template, just pass date range info
    return render_template(
        'main/daily_sales_report.html', # Reusing the template, maybe rename later
        title=f'Sales Report: {start_date.strftime("%d %b %Y")} to {end_date.strftime("%d %b %Y")}',
        data=report_data,
        start_date_str=start_date_str,
        end_date_str=end_date_str
    )

# --- Monthly Sales Report Route ---
@main_bp.route('/reports/monthly_sales')
@login_required
def monthly_sales_report():
    """Displays a sales report summarized by month for a selected year."""
    current_year = date.today().year
    try:
        report_year = int(request.args.get('year', current_year))
    except ValueError:
        report_year = current_year
        flash('Invalid year specified. Showing report for current year.', 'warning')

    # Query sales data for the selected year, extracting month and summing totals
    monthly_sales_data = db.session.query(
        extract('year', Sale.sale_timestamp).label('sale_year'),
        extract('month', Sale.sale_timestamp).label('sale_month'),
        func.sum(Sale.final_amount).label('total_sales'),
        func.sum(Sale.discount_total).label('total_discount'),
        func.count(Sale.id).label('order_count')
    ).filter(
        extract('year', Sale.sale_timestamp) == report_year
    ).group_by('sale_year', 'sale_month')\
     .order_by('sale_year', 'sale_month')\
     .all() # Returns list of Row objects

    # Format data for template (e.g., dictionary with month name as key)
    report_summary = {}
    grand_total_sales = 0.0
    grand_total_discount = 0.0
    grand_total_orders = 0

    for row in monthly_sales_data:
        month_num = int(row.sale_month)
        month_name = date(report_year, month_num, 1).strftime('%B') # Get month name
        report_summary[month_num] = {
            'month_name': month_name,
            'total_sales': row.total_sales or 0.0,
            'total_discount': row.total_discount or 0.0,
            'order_count': row.order_count or 0
        }
        grand_total_sales += report_summary[month_num]['total_sales']
        grand_total_discount += report_summary[month_num]['total_discount']
        grand_total_orders += report_summary[month_num]['order_count']

    # Get available years with sales data for the dropdown selector
    available_years = db.session.query(
        extract('year', Sale.sale_timestamp).label('sale_year')
    ).distinct().order_by(db.desc('sale_year')).all()
    years = [y.sale_year for y in available_years if y.sale_year] # Extract year numbers

    return render_template(
        'main/monthly_sales_report.html',
        title=f'Monthly Sales Report - {report_year}',
        report_year=report_year,
        report_summary=report_summary, # Dict keyed by month number
        grand_total_sales=grand_total_sales,
        grand_total_discount=grand_total_discount,
        grand_total_orders=grand_total_orders,
        available_years=years
    )

# --- Product Sales Report Route ---
@main_bp.route('/reports/product_sales')
@login_required
def product_sales_report():
    """Displays a report summarizing sales per product within a date range."""
    # Get dates from query parameters, default to last 7 days
    today = date.today()
    default_start = today - timedelta(days=6)
    start_date_str = request.args.get('start_date', default_start.isoformat())
    end_date_str = request.args.get('end_date', today.isoformat())

    try:
        start_date = date.fromisoformat(start_date_str)
        end_date = date.fromisoformat(end_date_str)
        if start_date > end_date:
            flash('Start date cannot be after end date. Using start date for both.', 'warning')
            end_date = start_date
            end_date_str = start_date_str
    except ValueError:
        flash('Invalid date format provided. Showing report for last 7 days.', 'warning')
        start_date = default_start
        end_date = today
        start_date_str = start_date.isoformat()
        end_date_str = end_date.isoformat()

    # Calculate start and end timestamps
    start_dt = datetime.combine(start_date, datetime.min.time())
    end_dt = datetime.combine(end_date, datetime.max.time())

    # Query to get sales data grouped by product
    product_sales_query = db.session.query(
        Product.id.label('product_id'),
        Product.name.label('product_name'),
        Product.barcode.label('product_barcode'),
        func.sum(SaleItem.quantity).label('total_quantity_sold'),
        # Calculate total net revenue per product (price*qty - discount)
        func.sum((SaleItem.quantity * SaleItem.price_at_sale) - SaleItem.discount_applied).label('total_revenue')
    ).join(SaleItem, SaleItem.product_id == Product.id)\
     .join(Sale, Sale.id == SaleItem.sale_id)\
     .filter(
         Sale.sale_timestamp >= start_dt,
         Sale.sale_timestamp <= end_dt
     )\
     .group_by(Product.id, Product.name, Product.barcode)\
     .order_by(db.desc('total_revenue')) # Order by revenue, descending

    # Execute query
    product_sales_data = product_sales_query.all() # Returns list of Row objects

    # Prepare data for the template
    report_data = {
        'start_date': start_date,
        'end_date': end_date,
        'product_sales': product_sales_data
    }

    return render_template(
        'main/product_sales_report.html',
        title=f'Product Sales Report: {start_date.strftime("%d %b %Y")} to {end_date.strftime("%d %b %Y")}',
        data=report_data,
        start_date_str=start_date_str,
        end_date_str=end_date_str
    )

# Add other main routes here if needed (e.g., profile page)