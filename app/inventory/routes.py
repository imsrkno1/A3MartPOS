# app/inventory/routes.py
from flask import render_template, redirect, url_for, flash, request, current_app, jsonify, Response, abort, session # Added session
from flask_login import login_required, current_user
from sqlalchemy import or_
from datetime import datetime

from . import inventory_bp # Import the blueprint instance
from ..models import Product, Purchase, PurchaseItem # Import relevant models
from ..forms import ProductForm, PurchaseForm # Import forms
from .. import db # Import the database instance
from ..utils import generate_barcode_logic, generate_barcode_sticker_pdf # Import utilities

# --- Product Routes ---

@inventory_bp.route('/products')
@login_required
def list_products():
    """Displays a list of products with search and pagination."""
    page = request.args.get('page', 1, type=int)
    query = request.args.get('query', '')
    low_stock_filter = request.args.get('low_stock', 'false').lower() == 'true'

    products_query = Product.query.order_by(Product.name.asc())

    if query:
        search_term = f"%{query}%"
        products_query = products_query.filter(
            or_(
                Product.name.ilike(search_term),
                Product.barcode.ilike(search_term),
                Product.sku.ilike(search_term),
                Product.category.ilike(search_term),
                Product.brand.ilike(search_term)
            )
        )

    if low_stock_filter:
        products_query = products_query.filter(
             Product.stock_quantity <= Product.low_stock_threshold,
             Product.is_active == True
        )

    pagination = products_query.paginate(
        page=page, per_page=current_app.config.get('ITEMS_PER_PAGE', 15), error_out=False
    )
    products = pagination.items

    return render_template(
        'inventory/products.html',
        title='Products',
        products=products,
        pagination=pagination,
        query=query,
        low_stock=low_stock_filter
    )


@inventory_bp.route('/products/add', methods=['GET', 'POST'])
@login_required
def add_product():
    """Handles adding a new product."""
    form = ProductForm()
    if form.validate_on_submit():
        barcode_to_save = form.barcode.data
        if not barcode_to_save:
            try:
                 barcode_to_save = generate_barcode_logic()
                 if not barcode_to_save:
                      flash('Could not automatically generate a unique barcode. Please enter one manually or check logs.', 'warning')
                      return render_template('inventory/product_form.html', title='Add Product', form=form, form_action='Add')
            except Exception as e:
                 current_app.logger.error(f"Barcode generation failed: {e}")
                 flash(f'Error generating barcode. Please enter one manually.', 'danger')
                 return render_template('inventory/product_form.html', title='Add Product', form=form, form_action='Add')

        filters = []
        if barcode_to_save:
            filters.append(Product.barcode == barcode_to_save)
        if form.sku.data:
            filters.append(Product.sku == form.sku.data)

        if filters:
            existing_product = Product.query.filter(or_(*filters)).first()
            if existing_product:
                flash('A product with this Barcode or SKU already exists.', 'warning')
                return render_template('inventory/product_form.html', title='Add Product', form=form, form_action='Add')

        new_product = Product(
            name=form.name.data,
            description=form.description.data,
            barcode=barcode_to_save,
            sku=form.sku.data,
            category=form.category.data,
            brand=form.brand.data,
            purchase_price=form.purchase_price.data,
            selling_price=form.selling_price.data,
            stock_quantity=form.stock_quantity.data,
            low_stock_threshold=form.low_stock_threshold.data,
            discount_percent=form.discount_percent.data, # Make sure this is saved
            is_active=True
        )
        db.session.add(new_product)
        try:
            db.session.commit()
            flash(f'Product "{new_product.name}" added successfully!', 'success')
            return redirect(url_for('inventory.list_products'))
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error adding product: {e}")
            flash(f'Error adding product. Please check logs.', 'danger')

    return render_template('inventory/product_form.html', title='Add Product', form=form, form_action='Add')


@inventory_bp.route('/products/edit/<int:product_id>', methods=['GET', 'POST'])
@login_required
def edit_product(product_id):
    """Handles editing an existing product."""
    product = Product.query.get_or_404(product_id)
    form = ProductForm(obj=product)

    if form.validate_on_submit():
        new_barcode = form.barcode.data
        new_sku = form.sku.data

        conflict_filters = [Product.id != product_id]
        or_filters = []
        if new_barcode:
            or_filters.append(Product.barcode == new_barcode)
        if new_sku:
            or_filters.append(Product.sku == new_sku)

        if or_filters:
            conflict_filters.append(or_(*or_filters))
            conflict = Product.query.filter(*conflict_filters).first()
            if conflict:
                 flash('Another product with this Barcode or SKU already exists.', 'warning')
                 return render_template('inventory/product_form.html', title='Edit Product', form=form, product=product, form_action='Edit')

        product.name = form.name.data
        product.description = form.description.data
        product.barcode = new_barcode
        product.sku = new_sku
        product.category = form.category.data
        product.brand = form.brand.data
        product.purchase_price = form.purchase_price.data
        product.selling_price = form.selling_price.data
        product.low_stock_threshold = form.low_stock_threshold.data
        product.discount_percent = form.discount_percent.data # Make sure this is saved

        try:
            db.session.commit()
            flash(f'Product "{product.name}" updated successfully!', 'success')
            return redirect(url_for('inventory.list_products'))
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error updating product: {e}")
            flash(f'Error updating product. Please check logs.', 'danger')

    return render_template('inventory/product_form.html', title='Edit Product', form=form, product=product, form_action='Edit')


# --- Purchase Routes ---

@inventory_bp.route('/purchases')
@login_required
def list_purchases():
    """Displays a list of purchase entries with pagination."""
    page = request.args.get('page', 1, type=int)
    purchases_query = Purchase.query.order_by(Purchase.purchase_date.desc())
    pagination = purchases_query.paginate(
        page=page, per_page=current_app.config.get('ITEMS_PER_PAGE', 15), error_out=False
    )
    purchases = pagination.items
    return render_template(
        'inventory/purchases.html',
        title='Purchases',
        purchases=purchases,
        pagination=pagination
    )

@inventory_bp.route('/purchases/add', methods=['GET', 'POST'])
@login_required
def add_purchase():
    """Handles adding a new purchase record and its items."""
    form = PurchaseForm()
    prefill_items = None # Variable to hold prefill data

    if request.method == 'GET':
        # Check if prefill data exists in session from auto-order generation
        if 'prefill_purchase_items' in session:
            prefill_items = session.pop('prefill_purchase_items', None) # Get and remove from session
            if prefill_items:
                 flash('Low stock items added to purchase order. Please review quantities and costs.', 'info')

    if request.method == 'POST':
        data = request.get_json()
        if not data:
             flash('Invalid data received. Please ensure data is sent as JSON.', 'danger')
             return redirect(url_for('inventory.add_purchase'))

        supplier_name = data.get('supplier_name')
        invoice_number = data.get('invoice_number')
        notes = data.get('notes')
        items_data = data.get('items', [])

        if not items_data:
            flash('Cannot record a purchase with no items.', 'warning')
            return render_template('inventory/purchase_form.html', title='Record Purchase', form=form)

        total_cost = 0
        purchase_items_to_add = []
        stock_updates = []

        try:
            for item_data in items_data:
                product_id = item_data.get('product_id')
                quantity = item_data.get('quantity')
                cost_price = item_data.get('cost_price')

                if not all([product_id, quantity, cost_price is not None]):
                    raise ValueError("Missing data for one or more items (product_id, quantity, cost_price).")
                if int(quantity) <= 0 or float(cost_price) < 0:
                     raise ValueError("Item quantity must be positive and cost price cannot be negative.")

                product = Product.query.get(int(product_id))
                if not product:
                    raise ValueError(f"Product with ID {product_id} not found.")

                item_total = int(quantity) * float(cost_price)
                total_cost += item_total

                purchase_item = PurchaseItem(
                    product_id=product.id,
                    quantity=int(quantity),
                    cost_price=float(cost_price)
                )
                purchase_items_to_add.append(purchase_item)
                stock_updates.append({'product': product, 'quantity': int(quantity)})

        except ValueError as e:
            flash(f'Error processing items: {e}', 'danger')
            return render_template('inventory/purchase_form.html', title='Record Purchase', form=form)
        except Exception as e:
             flash(f'An unexpected error occurred: {e}', 'danger')
             current_app.logger.error(f"Unexpected error during purchase item processing: {e}")
             return render_template('inventory/purchase_form.html', title='Record Purchase', form=form)

        try:
            new_purchase = Purchase(
                supplier_name=supplier_name,
                invoice_number=invoice_number,
                total_cost=total_cost,
                notes=notes,
                user_id=current_user.id,
                purchase_date=datetime.utcnow()
            )
            db.session.add(new_purchase)
            db.session.flush()

            for item in purchase_items_to_add:
                item.purchase_id = new_purchase.id
                db.session.add(item)

            for update in stock_updates:
                update['product'].stock_quantity += update['quantity']

            db.session.commit()
            flash('Purchase recorded successfully!', 'success')
            return redirect(url_for('inventory.list_purchases'))

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error saving purchase: {e}")
            flash(f'Error saving purchase record: {e}', 'danger')
            return render_template('inventory/purchase_form.html', title='Record Purchase', form=form)

    # Handle GET Request
    # Pass prefill_items to the template if they exist
    return render_template('inventory/purchase_form.html', title='Record Purchase', form=form, prefill_items=prefill_items)


# --- Generate Low Stock Purchase Order Route ---
@inventory_bp.route('/inventory/generate-low-stock-order', methods=['POST'])
@login_required
def generate_low_stock_order():
    """Finds low stock items and redirects to purchase form with pre-filled data."""
    try:
        low_stock_products = Product.query.filter(
            Product.stock_quantity <= Product.low_stock_threshold,
            Product.is_active == True
        ).all()

        if not low_stock_products:
            flash('No items are currently below the low stock threshold.', 'info')
            return redirect(url_for('main.dashboard'))

        # ** MODIFIED: Use low_stock_threshold for quantity **
        prefill_items = []
        for p in low_stock_products:
            # Set order quantity to the product's threshold
            # Ensure threshold is positive, default to 1 if not set or zero
            order_qty = p.low_stock_threshold if p.low_stock_threshold and p.low_stock_threshold > 0 else 1

            prefill_items.append({
                'product_id': p.id,
                'name': p.name, # Include name for display in JS
                'quantity': order_qty, # Use threshold as quantity
                'cost_price': p.purchase_price or 0.0 # Use last known purchase price or 0
            })

        # Store the prefill data in the session
        session['prefill_purchase_items'] = prefill_items
        flash(f'Generated order draft for {len(prefill_items)} low stock items.', 'success')

    except Exception as e:
        current_app.logger.error(f"Error generating low stock order: {e}")
        flash('An error occurred while generating the low stock order.', 'danger')
        return redirect(url_for('main.dashboard'))

    # Redirect to the add purchase page
    return redirect(url_for('inventory.add_purchase'))


# --- Product Search API ---
@inventory_bp.route('/api/products/search')
@login_required
def search_products_api():
    """API endpoint to search products for dynamic forms."""
    query = request.args.get('q', '')
    limit = request.args.get('limit', 10, type=int)
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
    results = [
        {
            'id': p.id,
            'text': f"{p.name} (Barcode: {p.barcode or 'N/A'}, SKU: {p.sku or 'N/A'})",
            'name': p.name, 'barcode': p.barcode, 'sku': p.sku,
            'selling_price': p.selling_price, 'purchase_price': p.purchase_price,
            'stock_quantity': p.stock_quantity,
            'discount_percent': p.discount_percent
        } for p in products ]
    return jsonify(results)


# --- Barcode Sticker PDF Route ---
@inventory_bp.route('/products/stickers/pdf', methods=['POST'])
@login_required
def download_sticker_pdf():
    """Generates and downloads an A4 PDF with barcode stickers for selected products."""
    product_ids = request.form.getlist('product_ids')
    if not product_ids:
        flash('No products selected for sticker generation.', 'warning')
        return redirect(url_for('inventory.list_products'))

    try:
        int_product_ids = [int(pid) for pid in product_ids]
        products_to_print = Product.query.filter(Product.id.in_(int_product_ids)).all()
    except ValueError:
         flash('Invalid product selection.', 'danger')
         return redirect(url_for('inventory.list_products'))

    if not products_to_print:
        flash('Selected products not found.', 'warning')
        return redirect(url_for('inventory.list_products'))

    valid_products = [p for p in products_to_print if p.barcode]
    if not valid_products:
         flash('None of the selected products have barcodes assigned.', 'warning')
         return redirect(url_for('inventory.list_products'))

    pdf_buffer = generate_barcode_sticker_pdf(valid_products)

    if pdf_buffer is None:
        flash('Error generating barcode sticker PDF.', 'danger')
        return redirect(url_for('inventory.list_products'))

    response = Response(pdf_buffer.getvalue(), mimetype='application/pdf')
    response.headers['Content-Disposition'] = f'attachment; filename=Barcode_Stickers_{datetime.now().strftime("%Y%m%d")}.pdf'
    return response
