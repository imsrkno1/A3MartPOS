# app/main/routes.py
from flask import render_template, redirect, url_for, flash, request, current_app, Response
from flask_login import login_required, current_user
from sqlalchemy import func, extract
from sqlalchemy.orm import joinedload
from collections import defaultdict
import pandas as pd
import io

from . import main_bp
from ..models import Sale, Product, SaleItem, Customer
from .. import db
from datetime import datetime, date, timedelta

@main_bp.route('/')
@main_bp.route('/dashboard')
@login_required
def dashboard():
    """Renders the main dashboard page with enhanced metrics and optional export for near expiry."""

    # Check for export request specifically for near expiry items
    export_format_near_expiry = request.args.get('export_near_expiry')
    today = date.today() # Define today once

    # --- Near Expiry Items Query (needed for both display and export) ---
    expiry_alert_days = 10
    near_expiry_date_limit = today + timedelta(days=expiry_alert_days)
    near_expiry_items_query = Product.query.filter(
        Product.expiry_date != None,
        Product.expiry_date >= today,
        Product.expiry_date <= near_expiry_date_limit,
        Product.is_active == True,
        Product.stock_quantity > 0
    ).order_by(Product.expiry_date.asc())

    if export_format_near_expiry == 'excel':
        near_expiry_items_data = near_expiry_items_query.all()
        if not near_expiry_items_data:
            flash('No near expiry items to export.', 'info')
            return redirect(url_for('main.dashboard')) # Redirect back to dashboard

        export_data_list = [
            {
                'Product ID': p.id,
                'Product Name': p.name,
                'Barcode': p.barcode or 'N/A',
                'SKU': p.sku or 'N/A',
                'Stock Quantity': p.stock_quantity,
                'Expiry Date': p.expiry_date.strftime('%Y-%m-%d') if p.expiry_date else 'N/A',
                'Days to Expire': (p.expiry_date - today).days if p.expiry_date else 'N/A'
            } for p in near_expiry_items_data
        ]
        df = pd.DataFrame(export_data_list)
        output = io.BytesIO()
        writer = pd.ExcelWriter(output, engine='openpyxl')
        try:
            df.to_excel(writer, index=False, sheet_name='Near_Expiry_Items')
        finally:
            writer.close()
        output.seek(0)
        return Response(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            headers={'Content-Disposition': f'attachment;filename=near_expiry_items_{today.isoformat()}.xlsx'}
        )

    # --- Proceed with normal dashboard data fetching if not exporting near expiry ---
    today_start = datetime.combine(today, datetime.min.time())
    today_end = datetime.combine(today, datetime.max.time())
    current_month_start = today.replace(day=1)
    next_month_start = (current_month_start + timedelta(days=32)).replace(day=1)
    current_month_end = next_month_start - timedelta(days=1)
    current_month_end_dt = datetime.combine(current_month_end, datetime.max.time())

    todays_sales_query = db.session.query( func.sum(Sale.final_amount).label('total_sales'), func.count(Sale.id).label('order_count') ).filter( Sale.sale_timestamp >= today_start, Sale.sale_timestamp <= today_end )
    todays_summary = todays_sales_query.first()
    todays_sales_total = todays_summary.total_sales if todays_summary and todays_summary.total_sales is not None else 0.0
    todays_order_count = todays_summary.order_count if todays_summary and todays_summary.order_count is not None else 0

    monthly_sales_query = db.session.query( func.sum(Sale.final_amount).label('total_sales') ).filter( Sale.sale_timestamp >= datetime.combine(current_month_start, datetime.min.time()), Sale.sale_timestamp <= current_month_end_dt )
    sales_this_month_total = monthly_sales_query.scalar() or 0.0

    top_items_query = db.session.query( Product.name, func.sum(SaleItem.quantity).label('total_quantity') ).join(SaleItem, SaleItem.product_id == Product.id).join(Sale, Sale.id == SaleItem.sale_id).filter(Sale.sale_timestamp >= today_start, Sale.sale_timestamp <= today_end).group_by(Product.name).order_by(db.desc('total_quantity')).limit(5)
    top_items_result = top_items_query.all()
    top_items_serializable = [(row[0], row[1]) for row in top_items_result]

    low_stock_items = Product.query.filter( Product.stock_quantity <= Product.low_stock_threshold, Product.is_active == True ).order_by(Product.stock_quantity.asc()).limit(10).all()
    new_customers_today = Customer.query.filter( Customer.created_at >= today_start, Customer.created_at <= today_end ).count()
    total_customers = Customer.query.count()
    total_active_products = Product.query.filter_by(is_active=True).count()
    total_stock_value_query = db.session.query( func.sum(Product.stock_quantity * func.coalesce(Product.purchase_price, 0)) ).filter(Product.is_active == True, Product.stock_quantity > 0)
    total_stock_value = total_stock_value_query.scalar() or 0.0
    
    near_expiry_items = near_expiry_items_query.limit(10).all() # Limit for display on dashboard

    dashboard_data = {
        'todays_sales': todays_sales_total, 'todays_orders': todays_order_count,
        'sales_this_month': sales_this_month_total, 'new_customers_today': new_customers_today,
        'total_customers': total_customers, 'total_active_products': total_active_products,
        'total_stock_value': total_stock_value, 'top_items': top_items_serializable,
        'low_stock_items': low_stock_items, 'near_expiry_items': near_expiry_items
    }
    return render_template('main/dashboard.html', title='Dashboard', data=dashboard_data)


# --- Sales Report by Date Range Route ---
@main_bp.route('/reports/sales_by_date')
@login_required
def sales_by_date_report():
    today_iso = date.today().isoformat()
    start_date_str = request.args.get('start_date', today_iso)
    end_date_str = request.args.get('end_date', today_iso)
    export_format = request.args.get('export')
    try:
        start_date_obj = date.fromisoformat(start_date_str); end_date_obj = date.fromisoformat(end_date_str)
        if start_date_obj > end_date_obj:
            flash('Start date cannot be after end date. Using start date for both.', 'warning')
            end_date_obj = start_date_obj; end_date_str = start_date_str
    except ValueError:
        flash('Invalid date format. Showing report for today.', 'warning')
        start_date_obj = date.today(); end_date_obj = date.today()
        start_date_str = end_date_str = start_date_obj.isoformat()
    start_dt = datetime.combine(start_date_obj, datetime.min.time()); end_dt = datetime.combine(end_date_obj, datetime.max.time())
    sales_in_range_query = Sale.query.options( joinedload(Sale.customer), joinedload(Sale.user) ).filter( Sale.sale_timestamp >= start_dt, Sale.sale_timestamp <= end_dt ).order_by(Sale.sale_timestamp.asc())
    if export_format == 'excel':
        sales_data = sales_in_range_query.all()
        if not sales_data:
            flash('No data to export for the selected date range.', 'info')
            return redirect(url_for('main.sales_by_date_report', start_date=start_date_str, end_date=end_date_str))
        export_data_list = []
        for sale in sales_data:
            for item in sale.items:
                export_data_list.append({
                    'Sale ID': sale.id, 'Timestamp': sale.sale_timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                    'Customer': sale.customer.name if sale.customer else 'Walk-in',
                    'Product Name': item.product.name, 'Quantity': item.quantity,
                    'Price @ Sale': item.price_at_sale, 'Discount Applied': item.discount_applied,
                    'Net Amount (Item)': (item.quantity * item.price_at_sale) - item.discount_applied,
                    'Payment Method': sale.payment_method, 'Sold By': sale.user.username if sale.user else 'N/A' })
        df = pd.DataFrame(export_data_list); output = io.BytesIO()
        writer = pd.ExcelWriter(output, engine='openpyxl')
        try: df.to_excel(writer, index=False, sheet_name='Sales_Report')
        finally: writer.close()
        output.seek(0)
        return Response( output, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', headers={'Content-Disposition': f'attachment;filename=sales_report_{start_date_str}_to_{end_date_str}.xlsx'} )
    sales_in_range = sales_in_range_query.all()
    total_sales = sum(s.final_amount for s in sales_in_range); total_discount = sum(s.discount_total for s in sales_in_range); number_of_sales = len(sales_in_range)
    report_data = { 'start_date': start_date_obj, 'end_date': end_date_obj, 'sales': sales_in_range, 'total_sales': total_sales, 'total_discount': total_discount, 'number_of_sales': number_of_sales }
    return render_template( 'main/daily_sales_report.html', title=f'Sales Report: {start_date_obj.strftime("%d %b %Y")} to {end_date_obj.strftime("%d %b %Y")}', data=report_data, start_date_str=start_date_str, end_date_str=end_date_str )

# --- Monthly Sales Report Route ---
@main_bp.route('/reports/monthly_sales')
@login_required
def monthly_sales_report():
    current_year = date.today().year
    try: report_year = int(request.args.get('year', current_year))
    except ValueError: report_year = current_year; flash('Invalid year. Showing current year.', 'warning')
    export_format = request.args.get('export')
    monthly_sales_data_query = db.session.query( extract('year', Sale.sale_timestamp).label('sale_year'), extract('month', Sale.sale_timestamp).label('sale_month'), func.sum(Sale.final_amount).label('total_sales'), func.sum(Sale.discount_total).label('total_discount'), func.count(Sale.id).label('order_count') ).filter( extract('year', Sale.sale_timestamp) == report_year ).group_by('sale_year', 'sale_month').order_by('sale_year', 'sale_month')
    if export_format == 'excel':
        monthly_data = monthly_sales_data_query.all()
        if not monthly_data:
            flash(f'No sales data to export for the year {report_year}.', 'info')
            return redirect(url_for('main.monthly_sales_report', year=report_year))
        export_data_list = [ { 'Year': int(row.sale_year), 'Month': date(report_year, int(row.sale_month), 1).strftime('%B'), 'Number of Sales': row.order_count or 0, 'Total Sales (₹)': row.total_sales or 0.0, 'Total Discount (₹)': row.total_discount or 0.0 } for row in monthly_data ]
        df = pd.DataFrame(export_data_list); output = io.BytesIO()
        writer = pd.ExcelWriter(output, engine='openpyxl')
        try: df.to_excel(writer, index=False, sheet_name=f'Monthly_Sales_{report_year}')
        finally: writer.close()
        output.seek(0)
        return Response( output, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', headers={'Content-Disposition': f'attachment;filename=monthly_sales_report_{report_year}.xlsx'} )
    monthly_sales_data = monthly_sales_data_query.all()
    report_summary = {}; grand_total_sales = 0.0; grand_total_discount = 0.0; grand_total_orders = 0
    for row in monthly_sales_data:
        month_num = int(row.sale_month); month_name = date(report_year, month_num, 1).strftime('%B')
        report_summary[month_num] = { 'month_name': month_name, 'total_sales': row.total_sales or 0.0, 'total_discount': row.total_discount or 0.0, 'order_count': row.order_count or 0 }
        grand_total_sales += report_summary[month_num]['total_sales']; grand_total_discount += report_summary[month_num]['total_discount']; grand_total_orders += report_summary[month_num]['order_count']
    available_years = db.session.query( extract('year', Sale.sale_timestamp).label('sale_year') ).distinct().order_by(db.desc('sale_year')).all()
    years = [y.sale_year for y in available_years if y.sale_year]
    return render_template( 'main/monthly_sales_report.html', title=f'Monthly Sales Report - {report_year}', report_year=report_year, report_summary=report_summary, grand_total_sales=grand_total_sales, grand_total_discount=grand_total_discount, grand_total_orders=grand_total_orders, available_years=years )

# --- Product Sales Report Route ---
@main_bp.route('/reports/product_sales')
@login_required
def product_sales_report():
    today = date.today(); default_start = today - timedelta(days=6)
    start_date_str = request.args.get('start_date', default_start.isoformat()); end_date_str = request.args.get('end_date', today.isoformat())
    export_format = request.args.get('export')
    try:
        start_date_obj = date.fromisoformat(start_date_str); end_date_obj = date.fromisoformat(end_date_str)
        if start_date_obj > end_date_obj:
            flash('Start date cannot be after end date. Using start date for both.', 'warning')
            end_date_obj = start_date_obj; end_date_str = start_date_str
    except ValueError:
        flash('Invalid date format. Showing report for last 7 days.', 'warning')
        start_date_obj = default_start; end_date_obj = today
        start_date_str = start_date_obj.isoformat(); end_date_str = end_date_obj.isoformat()
    start_dt = datetime.combine(start_date_obj, datetime.min.time()); end_dt = datetime.combine(end_date_obj, datetime.max.time())
    product_sales_query = db.session.query( Product.id.label('product_id'), Product.name.label('product_name'), Product.barcode.label('product_barcode'), Product.category.label('product_category'), Product.brand.label('product_brand'), func.sum(SaleItem.quantity).label('total_quantity_sold'), func.sum((SaleItem.quantity * SaleItem.price_at_sale) - SaleItem.discount_applied).label('total_revenue') ).join(SaleItem, SaleItem.product_id == Product.id).join(Sale, Sale.id == SaleItem.sale_id).filter( Sale.sale_timestamp >= start_dt, Sale.sale_timestamp <= end_dt ).group_by(Product.id, Product.name, Product.barcode, Product.category, Product.brand).order_by(db.desc('total_revenue'))
    if export_format == 'excel':
        product_sales_data = product_sales_query.all()
        if not product_sales_data:
            flash('No product sales data to export for the selected date range.', 'info')
            return redirect(url_for('main.product_sales_report', start_date=start_date_str, end_date=end_date_str))
        export_data_list = [ { 'Product ID': p.product_id, 'Product Name': p.product_name, 'Barcode': p.product_barcode, 'Category': p.product_category, 'Brand': p.product_brand, 'Quantity Sold': p.total_quantity_sold, 'Total Revenue (Net) (₹)': p.total_revenue } for p in product_sales_data ]
        df = pd.DataFrame(export_data_list); output = io.BytesIO()
        writer = pd.ExcelWriter(output, engine='openpyxl')
        try: df.to_excel(writer, index=False, sheet_name='Product_Sales_Report')
        finally: writer.close()
        output.seek(0)
        return Response( output, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', headers={'Content-Disposition': f'attachment;filename=product_sales_{start_date_str}_to_{end_date_str}.xlsx'} )
    product_sales_data = product_sales_query.all()
    report_data = { 'start_date': start_date_obj, 'end_date': end_date_obj, 'product_sales': product_sales_data }
    return render_template( 'main/product_sales_report.html', title=f'Product Sales Report: {start_date_obj.strftime("%d %b %Y")} to {end_date_obj.strftime("%d %b %Y")}', data=report_data, start_date_str=start_date_str, end_date_str=end_date_str )
