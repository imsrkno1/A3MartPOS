# app/billing/routes.py
from flask import render_template, redirect, url_for, flash, request, current_app, jsonify, Response, abort
from flask_login import login_required, current_user
from sqlalchemy import or_
from sqlalchemy.orm import joinedload
from datetime import datetime

from . import billing_bp
from ..models import Product, Customer, Sale, SaleItem, SaleReturn, SaleReturnItem
from .. import db
from ..utils import generate_a4_invoice_pdf, generate_thermal_receipt

@billing_bp.route('/billing')
@login_required
def billing_page():
    return render_template('billing/billing.html', title='Billing')


@billing_bp.route('/billing/process', methods=['POST'])
@login_required
def process_sale():
    current_app.logger.info("--- process_sale route initiated ---")
    data = request.get_json()
    if not data:
        current_app.logger.error("Invalid data format: No JSON data received.")
        return jsonify({'status': 'error', 'message': 'Invalid data format. JSON expected.'}), 400
    
    current_app.logger.info(f"Received sale data: {data}")

    items_data = data.get('items', [])
    customer_id = data.get('customer_id')
    payment_method = data.get('payment_method', 'Cash')
    notes = data.get('notes')

    if not items_data:
         current_app.logger.warning("Attempted to process sale with no items.")
         return jsonify({'status': 'error', 'message': 'Cannot process a sale with no items.'}), 400

    sale_items_to_add = []
    stock_updates = []
    subtotal = 0.0
    total_discount = 0.0

    current_app.logger.info("Starting item processing loop...")
    try:
        for i, item_data in enumerate(items_data):
            current_app.logger.info(f"Processing item {i+1}: {item_data}")
            product_id = item_data.get('product_id')
            quantity = item_data.get('quantity')
            price_at_sale = item_data.get('price_at_sale')
            discount_applied = item_data.get('discount_applied', 0.0)

            if not all([product_id, quantity, price_at_sale is not None]):
                raise ValueError(f"Item {i+1}: Missing data (product_id, quantity, or price_at_sale).")
            if int(quantity) <= 0 or float(price_at_sale) < 0 or float(discount_applied) < 0:
                 raise ValueError(f"Item {i+1}: Quantity must be positive and prices/discounts non-negative.")

            product = Product.query.get(int(product_id))
            if not product:
                raise ValueError(f"Item {i+1}: Product with ID {product_id} not found.")
            
            current_app.logger.info(f"Item {i+1} - Product '{product.name}': Current stock {product.stock_quantity}, Requested {quantity}")
            if product.stock_quantity < int(quantity):
                 raise ValueError(f"Insufficient stock for product '{product.name}'. Available: {product.stock_quantity}, Requested: {quantity}")

            item_subtotal = int(quantity) * float(price_at_sale)
            subtotal += item_subtotal
            total_discount += float(discount_applied)

            sale_item = SaleItem(
                product_id=product.id, quantity=int(quantity),
                price_at_sale=float(price_at_sale), discount_applied=float(discount_applied)
            )
            sale_items_to_add.append(sale_item)
            stock_updates.append({'product': product, 'quantity': int(quantity)})
        current_app.logger.info("Item processing loop completed.")
    except ValueError as e:
         current_app.logger.error(f"Sale processing validation error during item loop: {e}")
         return jsonify({'status': 'error', 'message': str(e)}), 400
    except Exception as e:
         current_app.logger.error(f"Unexpected error during sale item processing: {e}", exc_info=True)
         return jsonify({'status': 'error', 'message': 'An unexpected error occurred processing items.'}), 500

    final_amount = subtotal - total_discount
    if final_amount < 0: final_amount = 0
    current_app.logger.info(f"Calculated totals: Subtotal={subtotal}, Discount={total_discount}, Final={final_amount}")

    try:
        current_app.logger.info("Attempting to create Sale record...")
        customer = None
        if customer_id:
            customer = Customer.query.get(int(customer_id))
            current_app.logger.info(f"Customer fetched: {customer.name if customer else 'None'}")

        new_sale = Sale(
            sale_timestamp=datetime.utcnow(), total_amount=subtotal, discount_total=total_discount,
            final_amount=final_amount, payment_method=payment_method, notes=notes,
            user_id=current_user.id, customer_id=customer.id if customer else None
        )
        db.session.add(new_sale)
        current_app.logger.info("Sale object added to session. Flushing session...")
        db.session.flush() # Get the new_sale.id
        current_app.logger.info(f"Sale flushed, new_sale.id: {new_sale.id}. Adding sale items...")

        for item in sale_items_to_add:
            item.sale_id = new_sale.id
            db.session.add(item)
        current_app.logger.info("Sale items added to session. Updating stock...")

        for update in stock_updates:
            product_to_update = db.session.merge(update['product']) # Ensure product is in current session
            current_app.logger.info(f"Updating stock for {product_to_update.name}: current {product_to_update.stock_quantity}, change -{update['quantity']}")
            if product_to_update.stock_quantity >= update['quantity']:
                 product_to_update.stock_quantity -= update['quantity']
            else:
                 db.session.rollback()
                 current_app.logger.error(f"Stock level discrepancy for {product_to_update.name} during final save.")
                 raise ValueError(f"Stock level discrepancy for {product_to_update.name} during final save.")
        current_app.logger.info("Stock updates prepared. Attempting commit...")
        db.session.commit()
        current_app.logger.info(f"Sale {new_sale.id} committed successfully.")

        receipt_items = []
        for item in new_sale.items:
             item_total_before_discount = item.quantity * item.price_at_sale
             discount_percent = 0.0
             if item_total_before_discount > 0 and item.discount_applied > 0:
                 discount_percent = (item.discount_applied / item_total_before_discount) * 100
             receipt_items.append({
                'name': item.product.name, 'quantity': item.quantity, 'price': "%.2f" % item.price_at_sale,
                'item_total_before_discount': "%.2f" % item_total_before_discount,
                'discount_percent': "%.2f" % discount_percent, 'discount_amount': "%.2f" % item.discount_applied,
                'net_amount': "%.2f" % (item_total_before_discount - item.discount_applied) })
        receipt_data = {
            'sale_id': new_sale.id, 'timestamp': new_sale.sale_timestamp.isoformat(),
            'subtotal': "%.2f" % new_sale.total_amount, 'discount': "%.2f" % new_sale.discount_total,
            'total': "%.2f" % new_sale.final_amount, 'payment_method': new_sale.payment_method,
            'customer_name': new_sale.customer.name if new_sale.customer else None,
            'customer_phone': new_sale.customer.phone_number if new_sale.customer else None,
            'items': receipt_items
        }
        thermal_receipt_text = generate_thermal_receipt(receipt_data)
        return jsonify({
            'status': 'success', 'message': 'Sale processed successfully!',
            'receipt_data': receipt_data, 'thermal_receipt': thermal_receipt_text
            }), 200
    except ValueError as e: # Specific stock error from transaction or earlier
         db.session.rollback()
         current_app.logger.error(f"Error saving sale (ValueError): {e}", exc_info=True)
         return jsonify({'status': 'error', 'message': str(e)}), 400
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error saving sale (general Exception): {e}", exc_info=True)
        return jsonify({'status': 'error', 'message': 'Failed to save sale record due to an internal error.'}), 500

# ... (rest of the routes: download_invoice_pdf, list_sales, view_sale, process_return) ...
@billing_bp.route('/invoice/pdf/<int:sale_id>')
@login_required
def download_invoice_pdf(sale_id):
    sale = Sale.query.get_or_404(sale_id)
    sale_data_for_pdf = {
        'sale_id': sale.id, 'timestamp': sale.sale_timestamp.isoformat(),
        'subtotal': "%.2f" % sale.total_amount, 'discount': "%.2f" % sale.discount_total,
        'total': "%.2f" % sale.final_amount, 'payment_method': sale.payment_method,
        'customer_name': sale.customer.name if sale.customer else None,
        'items': [ { 'name': item.product.name, 'quantity': item.quantity, 'price': "%.2f" % item.price_at_sale, 'item_total': "%.2f" % (item.quantity * item.price_at_sale - item.discount_applied) } for item in sale.items ]
    }
    pdf_buffer = generate_a4_invoice_pdf(sale_data_for_pdf)
    if pdf_buffer is None: flash('Error generating PDF invoice.', 'danger'); abort(500, description="Failed to generate PDF invoice.")
    response = Response(pdf_buffer.getvalue(), mimetype='application/pdf')
    response.headers['Content-Disposition'] = f'attachment; filename=Invoice_{sale.id}.pdf'
    return response

@billing_bp.route('/sales')
@login_required
def list_sales():
    page = request.args.get('page', 1, type=int); query = request.args.get('query', '')
    sales_query = Sale.query.order_by(Sale.sale_timestamp.desc())
    if query:
        search_term = f"%{query}%"
        sales_query = sales_query.outerjoin(Customer).filter( or_( Sale.id.like(search_term), Customer.name.ilike(search_term), Sale.payment_method.ilike(search_term) ) )
    pagination = sales_query.paginate( page=page, per_page=current_app.config.get('ITEMS_PER_PAGE', 15), error_out=False )
    sales = pagination.items
    return render_template( 'billing/sales.html', title='Sales History', sales=sales, pagination=pagination, query=query )

@billing_bp.route('/sales/view/<int:sale_id>')
@login_required
def view_sale(sale_id):
    sale = Sale.query.options( joinedload(Sale.customer), joinedload(Sale.user) ).get_or_404(sale_id)
    return render_template('billing/sale_detail.html', title=f'Sale Details #{sale.id}', sale=sale)

@billing_bp.route('/sales/return/<int:sale_id>', methods=['POST'])
@login_required
def process_return(sale_id):
    original_sale = Sale.query.options(joinedload(Sale.items).joinedload(SaleItem.product)).get_or_404(sale_id)
    existing_return = SaleReturn.query.filter_by(original_sale_id=original_sale.id).first()
    if existing_return:
        flash(f'A return has already been processed for Sale ID {original_sale.id}.', 'warning')
        return redirect(url_for('billing.view_sale', sale_id=sale_id))
    reason = request.form.get('return_reason', 'Full return processed'); total_refund = 0.0
    return_items_to_add = []; stock_updates = []
    try:
        for item in original_sale.items:
            amount_refunded_for_item = (item.quantity * item.price_at_sale) - item.discount_applied; total_refund += amount_refunded_for_item
            return_item = SaleReturnItem( product_id=item.product_id, quantity=item.quantity, amount_refunded=amount_refunded_for_item )
            return_items_to_add.append(return_item)
            stock_updates.append({'product': item.product, 'quantity': item.quantity})
        new_return = SaleReturn( return_timestamp=datetime.utcnow(), reason=reason, total_refunded_amount=total_refund, original_sale_id=original_sale.id, customer_id=original_sale.customer_id, processed_by_user_id=current_user.id )
        db.session.add(new_return); db.session.flush()
        for ret_item in return_items_to_add: ret_item.sale_return_id = new_return.id; db.session.add(ret_item)
        for update in stock_updates:
            product_to_update = db.session.merge(update['product'])
            product_to_update.stock_quantity += update['quantity']
        db.session.commit()
        flash(f'Return for Sale ID {original_sale.id} processed successfully. Stock updated.', 'success')
        return redirect(url_for('billing.view_sale', sale_id=sale_id))
    except Exception as e:
        db.session.rollback(); current_app.logger.error(f"Error processing return for Sale ID {sale_id}: {e}", exc_info=True)
        flash(f'An error occurred while processing the return: {e}', 'danger')
        return redirect(url_for('billing.view_sale', sale_id=sale_id))
