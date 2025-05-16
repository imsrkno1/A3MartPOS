# app/inventory/routes.py
from flask import render_template, redirect, url_for, flash, request, current_app, jsonify, Response, abort, session
from flask_login import login_required, current_user
from sqlalchemy import or_
from datetime import datetime, date, timedelta # Added date, timedelta
import os
from werkzeug.utils import secure_filename
import pandas as pd

from . import inventory_bp
from ..models import Product, Purchase, PurchaseItem, StockAdjustment
from ..forms import ProductForm, PurchaseForm, StockAdjustmentForm
from .. import db
from ..utils import generate_barcode_logic, generate_barcode_sticker_pdf

ALLOWED_EXTENSIONS = {'xlsx', 'xls'}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# --- Product Routes ---
@inventory_bp.route('/products')
@login_required
def list_products():
    page = request.args.get('page', 1, type=int)
    query = request.args.get('query', '')
    low_stock_filter = request.args.get('low_stock', 'false').lower() == 'true'
    products_query = Product.query.order_by(Product.name.asc())
    if query:
        search_term = f"%{query}%"
        products_query = products_query.filter(
            or_( Product.name.ilike(search_term), Product.barcode.ilike(search_term),
                 Product.sku.ilike(search_term), Product.category.ilike(search_term),
                 Product.brand.ilike(search_term) ))
    if low_stock_filter:
        products_query = products_query.filter(
             Product.stock_quantity <= Product.low_stock_threshold, Product.is_active == True )
    pagination = products_query.paginate( page=page, per_page=current_app.config.get('ITEMS_PER_PAGE', 15), error_out=False )
    products = pagination.items
    return render_template( 'inventory/products.html', title='Products', products=products,
                           pagination=pagination, query=query, low_stock=low_stock_filter )

@inventory_bp.route('/products/add', methods=['GET', 'POST'])
@login_required
def add_product():
    form = ProductForm()
    if form.validate_on_submit():
        barcode_to_save = form.barcode.data
        if not barcode_to_save:
            try:
                 barcode_to_save = generate_barcode_logic()
                 if not barcode_to_save:
                      flash('Could not automatically generate a unique barcode.', 'warning')
                      return render_template('inventory/product_form.html', title='Add Product', form=form, form_action='Add')
            except Exception as e:
                 current_app.logger.error(f"Barcode generation failed: {e}")
                 flash(f'Error generating barcode.', 'danger')
                 return render_template('inventory/product_form.html', title='Add Product', form=form, form_action='Add')
        filters = []
        if barcode_to_save: filters.append(Product.barcode == barcode_to_save)
        if form.sku.data: filters.append(Product.sku == form.sku.data)
        if filters:
            existing_product = Product.query.filter(or_(*filters)).first()
            if existing_product:
                flash('A product with this Barcode or SKU already exists.', 'warning')
                return render_template('inventory/product_form.html', title='Add Product', form=form, form_action='Add')
        new_product = Product( name=form.name.data, description=form.description.data, barcode=barcode_to_save,
            sku=form.sku.data, category=form.category.data, brand=form.brand.data, purchase_price=form.purchase_price.data,
            selling_price=form.selling_price.data, stock_quantity=form.stock_quantity.data,
            low_stock_threshold=form.low_stock_threshold.data, discount_percent=form.discount_percent.data, is_active=True,
            expiry_date=form.expiry_date.data )
        db.session.add(new_product)
        try:
            db.session.commit(); flash(f'Product "{new_product.name}" added successfully!', 'success')
            return redirect(url_for('inventory.list_products'))
        except Exception as e:
            db.session.rollback(); current_app.logger.error(f"Error adding product: {e}")
            flash(f'Error adding product.', 'danger')
    return render_template('inventory/product_form.html', title='Add Product', form=form, form_action='Add')

@inventory_bp.route('/products/edit/<int:product_id>', methods=['GET', 'POST'])
@login_required
def edit_product(product_id):
    product = Product.query.get_or_404(product_id)
    form = ProductForm(obj=product)
    if form.validate_on_submit():
        new_barcode = form.barcode.data; new_sku = form.sku.data
        conflict_filters = [Product.id != product_id]; or_filters = []
        if new_barcode: or_filters.append(Product.barcode == new_barcode)
        if new_sku: or_filters.append(Product.sku == new_sku)
        if or_filters:
            conflict_filters.append(or_(*or_filters))
            conflict = Product.query.filter(*conflict_filters).first()
            if conflict:
                 flash('Another product with this Barcode or SKU already exists.', 'warning')
                 return render_template('inventory/product_form.html', title='Edit Product', form=form, product=product, form_action='Edit')
        product.name=form.name.data; product.description=form.description.data; product.barcode=new_barcode
        product.sku=new_sku; product.category=form.category.data; product.brand=form.brand.data
        product.purchase_price=form.purchase_price.data; product.selling_price=form.selling_price.data
        product.low_stock_threshold=form.low_stock_threshold.data; product.discount_percent=form.discount_percent.data
        product.expiry_date=form.expiry_date.data
        try:
            db.session.commit(); flash(f'Product "{product.name}" updated successfully!', 'success')
            return redirect(url_for('inventory.list_products'))
        except Exception as e:
            db.session.rollback(); current_app.logger.error(f"Error updating product: {e}")
            flash(f'Error updating product.', 'danger')
    if request.method == 'GET' and product.expiry_date:
        form.expiry_date.data = product.expiry_date
    return render_template('inventory/product_form.html', title='Edit Product', form=form, product=product, form_action='Edit')

# --- Purchase Routes ---
@inventory_bp.route('/purchases')
@login_required
def list_purchases():
    page = request.args.get('page', 1, type=int)
    purchases_query = Purchase.query.order_by(Purchase.purchase_date.desc())
    pagination = purchases_query.paginate( page=page, per_page=current_app.config.get('ITEMS_PER_PAGE', 15), error_out=False )
    purchases = pagination.items
    return render_template( 'inventory/purchases.html', title='Purchases', purchases=purchases, pagination=pagination )

@inventory_bp.route('/purchases/add', methods=['GET', 'POST'])
@login_required
def add_purchase():
    form = PurchaseForm(); prefill_items = None
    if request.method == 'GET':
        if 'prefill_purchase_items' in session:
            prefill_items = session.pop('prefill_purchase_items', None)
            if prefill_items: flash('Low stock items added to purchase order.', 'info')
    if request.method == 'POST':
        data = request.get_json()
        if not data: flash('Invalid data received.', 'danger'); return redirect(url_for('inventory.add_purchase'))
        supplier_name = data.get('supplier_name'); invoice_number = data.get('invoice_number')
        notes = data.get('notes'); items_data = data.get('items', [])
        if not items_data: flash('Cannot record a purchase with no items.', 'warning'); return render_template('inventory/purchase_form.html', title='Record Purchase', form=form)
        total_cost = 0; purchase_items_to_add = []; stock_updates = []
        try:
            for item_data in items_data:
                product_id = item_data.get('product_id'); quantity = item_data.get('quantity'); cost_price = item_data.get('cost_price')
                if not all([product_id, quantity, cost_price is not None]): raise ValueError("Missing data for items.")
                if int(quantity) <= 0 or float(cost_price) < 0: raise ValueError("Invalid quantity or cost price.")
                product = Product.query.get(int(product_id));
                if not product: raise ValueError(f"Product ID {product_id} not found.")
                item_total = int(quantity) * float(cost_price); total_cost += item_total
                purchase_item = PurchaseItem( product_id=product.id, quantity=int(quantity), cost_price=float(cost_price) )
                purchase_items_to_add.append(purchase_item)
                stock_updates.append({'product': product, 'quantity': int(quantity)})
        except ValueError as e: flash(f'Error processing items: {e}', 'danger'); return render_template('inventory/purchase_form.html', title='Record Purchase', form=form)
        except Exception as e: flash(f'An unexpected error occurred: {e}', 'danger'); current_app.logger.error(f"Purchase item processing error: {e}"); return render_template('inventory/purchase_form.html', title='Record Purchase', form=form)
        try:
            new_purchase = Purchase( supplier_name=supplier_name, invoice_number=invoice_number, total_cost=total_cost, notes=notes, user_id=current_user.id, purchase_date=datetime.utcnow() )
            db.session.add(new_purchase); db.session.flush()
            for item in purchase_items_to_add: item.purchase_id = new_purchase.id; db.session.add(item)
            for update in stock_updates: update['product'].stock_quantity += update['quantity']
            db.session.commit(); flash('Purchase recorded successfully!', 'success'); return redirect(url_for('inventory.list_purchases'))
        except Exception as e:
            db.session.rollback(); current_app.logger.error(f"Error saving purchase: {e}"); flash(f'Error saving purchase record: {e}', 'danger')
            return render_template('inventory/purchase_form.html', title='Record Purchase', form=form)
    return render_template('inventory/purchase_form.html', title='Record Purchase', form=form, prefill_items=prefill_items)

@inventory_bp.route('/inventory/generate-low-stock-order', methods=['POST'])
@login_required
def generate_low_stock_order():
    try:
        low_stock_products = Product.query.filter( Product.stock_quantity <= Product.low_stock_threshold, Product.is_active == True ).all()
        if not low_stock_products: flash('No items are currently below the low stock threshold.', 'info'); return redirect(url_for('main.dashboard'))
        prefill_items = []
        for p in low_stock_products:
            order_qty = p.low_stock_threshold if p.low_stock_threshold and p.low_stock_threshold > 0 else 1
            prefill_items.append({ 'product_id': p.id, 'name': p.name, 'quantity': order_qty, 'cost_price': p.purchase_price or 0.0 })
        session['prefill_purchase_items'] = prefill_items
        flash(f'Generated order draft for {len(prefill_items)} low stock items.', 'success')
    except Exception as e:
        current_app.logger.error(f"Error generating low stock order: {e}")
        flash('An error occurred while generating the low stock order.', 'danger')
        return redirect(url_for('main.dashboard'))
    return redirect(url_for('inventory.add_purchase'))

# --- Product Search API ---
@inventory_bp.route('/api/products/search')
@login_required
def search_products_api():
    """API endpoint to search products for dynamic forms."""
    query = request.args.get('q', ''); limit = request.args.get('limit', 10, type=int)
    today = date.today()
    expiry_alert_days = 10 # Consistent with dashboard logic
    near_expiry_date_limit = today + timedelta(days=expiry_alert_days)

    if not query: return jsonify([])
    search_term = f"%{query}%"
    products = Product.query.filter(
        Product.is_active == True,
        or_(
            Product.name.ilike(search_term),
            Product.barcode.ilike(search_term),
            Product.sku.ilike(search_term)
        )
    ).limit(limit).all()

    results = []
    for p in products:
        is_near_expiry = False
        if p.expiry_date and p.stock_quantity > 0: # Check if expiry_date is set and in stock
            if today <= p.expiry_date <= near_expiry_date_limit:
                is_near_expiry = True
        
        results.append({
            'id': p.id,
            'text': f"{p.name} (Barcode: {p.barcode or 'N/A'}, SKU: {p.sku or 'N/A'})",
            'name': p.name, 'barcode': p.barcode, 'sku': p.sku,
            'selling_price': p.selling_price, 'purchase_price': p.purchase_price,
            'stock_quantity': p.stock_quantity,
            'discount_percent': p.discount_percent,
            'brand': p.brand, # ** Added brand here as well if not already present **
            'is_near_expiry': is_near_expiry # ** ADDED: Near Expiry Flag **
        })
    return jsonify(results)


# --- Barcode Sticker PDF Route ---
@inventory_bp.route('/products/stickers/pdf', methods=['POST'])
@login_required
def download_sticker_pdf():
    product_ids_str = request.form.getlist('product_ids')
    if not product_ids_str: flash('No products selected.', 'warning'); return redirect(url_for('inventory.list_products'))
    products_data_for_pdf = []
    try:
        for pid_str in product_ids_str:
            product_id = int(pid_str)
            quantity_str = request.form.get(f'sticker_qty_{product_id}'); quantity = int(quantity_str) if quantity_str else 1
            if quantity < 1: quantity = 1
            product = Product.query.get(product_id)
            if product and product.barcode:
                for _ in range(quantity): products_data_for_pdf.append(product)
            elif product and not product.barcode: flash(f'Product "{product.name}" has no barcode.', 'info')
    except ValueError: flash('Invalid product selection or quantity.', 'danger'); return redirect(url_for('inventory.list_products'))
    if not products_data_for_pdf: flash('No valid products selected for stickers.', 'warning'); return redirect(url_for('inventory.list_products'))
    pdf_buffer = generate_barcode_sticker_pdf(products_data_for_pdf)
    if pdf_buffer is None: flash('Error generating barcode sticker PDF.', 'danger'); return redirect(url_for('inventory.list_products'))
    response = Response(pdf_buffer.getvalue(), mimetype='application/pdf')
    response.headers['Content-Disposition'] = f'attachment; filename=Barcode_Stickers_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf'
    return response

# --- Stock Adjustment Routes ---
@inventory_bp.route('/products/adjust/<int:product_id>', methods=['GET', 'POST'])
@login_required
def adjust_stock(product_id):
    product = Product.query.get_or_404(product_id)
    form = StockAdjustmentForm()
    if form.validate_on_submit():
        change = form.quantity_change.data; reason = form.reason.data; notes = form.notes.data
        if product.stock_quantity + change < 0 and reason not in ['Initial Stock', 'Correction', 'Damage', 'Theft']:
             flash(f'Adjustment would result in negative stock ({product.stock_quantity + change}). Please verify.', 'danger')
        else:
            try:
                stock_before = product.stock_quantity; stock_after = stock_before + change
                adjustment = StockAdjustment( product_id=product.id, user_id=current_user.id, quantity_change=change, reason=reason, notes=notes, stock_level_before=stock_before, stock_level_after=stock_after )
                product.stock_quantity = stock_after
                db.session.add(adjustment); db.session.commit()
                flash(f'Stock for "{product.name}" adjusted by {change}. New stock: {stock_after}.', 'success')
                return redirect(url_for('inventory.list_products'))
            except Exception as e:
                db.session.rollback(); current_app.logger.error(f"Error adjusting stock for product {product_id}: {e}")
                flash(f'An error occurred while adjusting stock: {e}', 'danger')
    form.product_id.data = product.id; form.product_name.data = product.name; form.current_stock.data = product.stock_quantity
    if request.method == 'GET': form.quantity_change.data = None
    return render_template('inventory/stock_adjustment_form.html', title=f'Adjust Stock - {product.name}', form=form, product=product)

@inventory_bp.route('/stock/adjustments')
@login_required
def list_stock_adjustments():
    page = request.args.get('page', 1, type=int)
    adjustments_query = StockAdjustment.query.order_by(StockAdjustment.timestamp.desc())
    pagination = adjustments_query.paginate( page=page, per_page=current_app.config.get('ITEMS_PER_PAGE', 20), error_out=False )
    adjustments = pagination.items
    return render_template('inventory/adjustments_history.html', title='Stock Adjustment History', adjustments=adjustments, pagination=pagination)

@inventory_bp.route('/stock/bulk-upload', methods=['GET', 'POST'])
@login_required
def bulk_upload_stock():
    if request.method == 'POST':
        if 'stock_file' not in request.files: flash('No file part in the request.', 'danger'); return redirect(request.url)
        file = request.files['stock_file']
        if file.filename == '': flash('No selected file.', 'warning'); return redirect(request.url)
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            try:
                excel_data = pd.read_excel(file.stream, engine='openpyxl')
                required_qty_col = 'NewQuantity'; identifier_col = None
                if 'Barcode' in excel_data.columns: identifier_col = 'Barcode'
                elif 'SKU' in excel_data.columns: identifier_col = 'SKU'
                elif 'ProductID' in excel_data.columns: identifier_col = 'ProductID'
                if not identifier_col or required_qty_col not in excel_data.columns:
                     flash(f'Excel file must contain "{required_qty_col}" and one of "Barcode", "SKU", or "ProductID".', 'danger')
                     return redirect(request.url)
                updated_count = 0; skipped_count = 0; errors = []
                for index, row in excel_data.iterrows():
                    identifier_value = row[identifier_col]; new_quantity_val = row[required_qty_col]
                    if pd.isna(identifier_value) or pd.isna(new_quantity_val):
                        skipped_count += 1; errors.append(f"Row {index+2}: Skipped missing data."); continue
                    try:
                        new_quantity = int(new_quantity_val)
                        if new_quantity < 0: raise ValueError("Quantity cannot be negative.")
                    except (ValueError, TypeError):
                        skipped_count += 1; errors.append(f"Row {index+2}: Invalid quantity '{new_quantity_val}'. Must be a whole non-negative number."); continue
                    product = None
                    if identifier_col == 'Barcode': product = Product.query.filter_by(barcode=str(identifier_value)).first()
                    elif identifier_col == 'SKU': product = Product.query.filter_by(sku=str(identifier_value)).first()
                    elif identifier_col == 'ProductID':
                         try: product = Product.query.get(int(identifier_value))
                         except ValueError: product = None
                    if product:
                        stock_before = product.stock_quantity; change = new_quantity - stock_before
                        adjustment = StockAdjustment( product_id=product.id, user_id=current_user.id, quantity_change=change, reason="Bulk Upload", notes=f"File: {filename}", stock_level_before=stock_before, stock_level_after=new_quantity )
                        product.stock_quantity = new_quantity; db.session.add(adjustment); updated_count += 1
                    else: skipped_count += 1; errors.append(f"Row {index+2}: Product {identifier_col} '{identifier_value}' not found.")
                db.session.commit()
                flash(f'Bulk upload: Updated {updated_count}, Skipped {skipped_count}.', 'success')
                if errors:
                    flash('Details for skipped rows:', 'warning')
                    for error_msg in errors[:10]: flash(error_msg, 'info')
                    if len(errors) > 10: flash(f"... and {len(errors)-10} more errors.", 'info')
                return redirect(url_for('inventory.list_products'))
            except Exception as e:
                db.session.rollback(); current_app.logger.error(f"Error processing bulk upload {filename}: {e}")
                flash(f'Error processing file: {e}', 'danger'); return redirect(request.url)
        else: flash('Invalid file type. Only .xlsx or .xls allowed.', 'danger'); return redirect(request.url)
    return render_template('inventory/bulk_upload_stock.html', title='Bulk Stock Upload')

4