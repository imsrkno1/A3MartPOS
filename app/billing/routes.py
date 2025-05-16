# app/billing/routes.py
from flask import render_template, redirect, url_for, flash, request, current_app, jsonify, Response, abort # Added Response, abort
from flask_login import login_required, current_user
# **MODIFIED: Import joinedload separately if needed elsewhere, but remove from view_sale query options for Sale.items**
from sqlalchemy import or_
from sqlalchemy.orm import joinedload # Import joinedload if needed for other relationships
from datetime import datetime

from . import billing_bp # Import the blueprint instance
# ** MODIFIED: Import SaleReturn, SaleReturnItem **
from ..models import Product, Customer, Sale, SaleItem, SaleReturn, SaleReturnItem
from .. import db # Import the database instance
from ..utils import generate_a4_invoice_pdf, generate_thermal_receipt # Import utility functions

@billing_bp.route('/billing')
@login_required
def billing_page():
    """Displays the main billing interface."""
    return render_template('billing/billing.html', title='Billing')


@billing_bp.route('/billing/process', methods=['POST'])
@login_required
def process_sale():
    """Processes the submitted sale data from the billing interface."""
    data = request.get_json()
    if not data:
        return jsonify({'status': 'error', 'message': 'Invalid data format. JSON expected.'}), 400

    items_data = data.get('items', [])
    customer_id = data.get('customer_id') # Can be None if no customer selected
    payment_method = data.get('payment_method', 'Cash')
    notes = data.get('notes')

    if not items_data:
         return jsonify({'status': 'error', 'message': 'Cannot process a sale with no items.'}), 400

    # --- Data Validation and Calculation ---
    sale_items_to_add = []
    stock_updates = []
    subtotal = 0.0
    total_discount = 0.0

    try:
        for item_data in items_data:
            product_id = item_data.get('product_id')
            quantity = item_data.get('quantity')
            price_at_sale = item_data.get('price_at_sale') # Price per unit used in the bill
            discount_applied = item_data.get('discount_applied', 0.0) # Discount amount for this line item

            if not all([product_id, quantity, price_at_sale is not None]): # Check price_at_sale explicitly for 0
                raise ValueError("Missing data for one or more items (product_id, quantity, price_at_sale).")
            if int(quantity) <= 0 or float(price_at_sale) < 0 or float(discount_applied) < 0:
                 raise ValueError("Item quantity must be positive and prices/discounts cannot be negative.")

            product = Product.query.get(int(product_id))
            if not product:
                raise ValueError(f"Product with ID {product_id} not found.")
            # Ensure stock check uses the most up-to-date value from DB within transaction
            if product.stock_quantity < int(quantity):
                 raise ValueError(f"Insufficient stock for product '{product.name}'. Available: {product.stock_quantity}, Requested: {quantity}")

            item_subtotal = int(quantity) * float(price_at_sale)
            subtotal += item_subtotal
            total_discount += float(discount_applied) # Accumulate line item discounts

            sale_item = SaleItem(
                product_id=product.id,
                quantity=int(quantity),
                price_at_sale=float(price_at_sale),
                discount_applied=float(discount_applied)
            )
            sale_items_to_add.append(sale_item)
            stock_updates.append({'product': product, 'quantity': int(quantity)})

    except ValueError as e:
         current_app.logger.warning(f"Sale processing validation error: {e}")
         return jsonify({'status': 'error', 'message': str(e)}), 400
    except Exception as e:
         current_app.logger.error(f"Unexpected error during sale item processing: {e}")
         return jsonify({'status': 'error', 'message': 'An unexpected error occurred processing items.'}), 500

    # --- Calculate Final Amount ---
    final_amount = subtotal - total_discount
    if final_amount < 0: final_amount = 0

    # --- Create Sale Record and Items in a Transaction ---
    try:
        new_sale = Sale(
            sale_timestamp=datetime.utcnow(),
            total_amount=subtotal,
            discount_total=total_discount,
            final_amount=final_amount,
            payment_method=payment_method,
            notes=notes,
            user_id=current_user.id,
            customer_id=int(customer_id) if customer_id else None
        )
        db.session.add(new_sale)
        db.session.flush()

        for item in sale_items_to_add:
            item.sale_id = new_sale.id
            db.session.add(item)

        for update in stock_updates:
            if update['product'].stock_quantity >= update['quantity']:
                 update['product'].stock_quantity -= update['quantity']
            else:
                 db.session.rollback()
                 raise ValueError(f"Stock level discrepancy for {update['product'].name} during final save.")

        # --- Success Response ---
        receipt_items = []
        for item in new_sale.items: # Access items after commit
             item_total_before_discount = item.quantity * item.price_at_sale
             discount_percent = 0.0
             if item_total_before_discount > 0 and item.discount_applied > 0:
                 discount_percent = (item.discount_applied / item_total_before_discount) * 100
             receipt_items.append({
                'name': item.product.name,
                'quantity': item.quantity,
                'price': "%.2f" % item.price_at_sale, # This is the MRP (price per unit)
                'item_total_before_discount': "%.2f" % item_total_before_discount,
                'discount_percent': "%.2f" % discount_percent,
                'discount_amount': "%.2f" % item.discount_applied,
                'net_amount': "%.2f" % (item_total_before_discount - item.discount_applied) # Net amount for the line
             })

        receipt_data = {
            'sale_id': new_sale.id,
            'timestamp': new_sale.sale_timestamp.isoformat(),
            'subtotal': "%.2f" % new_sale.total_amount,
            'discount': "%.2f" % new_sale.discount_total,
            'total': "%.2f" % new_sale.final_amount,
            'payment_method': new_sale.payment_method,
            'customer_name': new_sale.customer.name if new_sale.customer else None,
            'customer_phone': new_sale.customer.phone_number if new_sale.customer else None, # <<<--- THIS LINE IS CRUCIAL
            'items': receipt_items
        }

        current_app.logger.info(f"Sale {new_sale.id} processed successfully by user {current_user.username}.")
        thermal_receipt_text = generate_thermal_receipt(receipt_data)

        return jsonify({
            'status': 'success',
            'message': 'Sale processed successfully!',
            'receipt_data': receipt_data,
            'thermal_receipt': thermal_receipt_text
            }), 200

    except ValueError as e:
         db.session.rollback()
         current_app.logger.error(f"Error saving sale (stock check failed): {e}")
         return jsonify({'status': 'error', 'message': str(e)}), 400
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error saving sale (general): {e}")
        return jsonify({'status': 'error', 'message': f'Error saving sale record.'}), 500


@billing_bp.route('/invoice/pdf/<int:sale_id>')
@login_required
def download_invoice_pdf(sale_id):
    """Generates and downloads an A4 PDF invoice for a specific sale."""
    sale = Sale.query.get_or_404(sale_id)
    sale_data_for_pdf = {
        'sale_id': sale.id,
        'timestamp': sale.sale_timestamp.isoformat(),
        'subtotal': "%.2f" % sale.total_amount,
        'discount': "%.2f" % sale.discount_total,
        'total': "%.2f" % sale.final_amount,
        'payment_method': sale.payment_method,
        'customer_name': sale.customer.name if sale.customer else None,
        'items': [
            {
                'name': item.product.name,
                'quantity': item.quantity,
                'price': "%.2f" % item.price_at_sale,
                'item_total': "%.2f" % (item.quantity * item.price_at_sale - item.discount_applied) # Show net total for line item in PDF? Or keep gross? Showing Gross here.
             } for item in sale.items
        ]
    }
    pdf_buffer = generate_a4_invoice_pdf(sale_data_for_pdf)
    if pdf_buffer is None:
        flash('Error generating PDF invoice.', 'danger')
        abort(500, description="Failed to generate PDF invoice.")
    response = Response(pdf_buffer.getvalue(), mimetype='application/pdf')
    response.headers['Content-Disposition'] = f'attachment; filename=Invoice_{sale.id}.pdf'
    return response


# --- Sales List Route ---
@billing_bp.route('/sales')
@login_required
def list_sales():
    """Displays a list of past sales transactions with pagination."""
    page = request.args.get('page', 1, type=int)
    query = request.args.get('query', '')
    sales_query = Sale.query.order_by(Sale.sale_timestamp.desc())
    if query:
        search_term = f"%{query}%"
        sales_query = sales_query.outerjoin(Customer).filter(
             or_(
                 Sale.id.like(search_term),
                 Customer.name.ilike(search_term),
                 Sale.payment_method.ilike(search_term)
             )
         )
    pagination = sales_query.paginate(
        page=page, per_page=current_app.config.get('ITEMS_PER_PAGE', 15), error_out=False
    )
    sales = pagination.items
    return render_template(
        'billing/sales.html',
        title='Sales History',
        sales=sales,
        pagination=pagination,
        query=query
    )

# --- View Sale Detail Route ---
@billing_bp.route('/sales/view/<int:sale_id>')
@login_required
def view_sale(sale_id):
    """Displays the details of a specific sale."""
    # ** MODIFIED: Fetch sale first, then access items. Eager load customer/user. **
    sale = Sale.query.options(
        joinedload(Sale.customer), # Eager load customer
        joinedload(Sale.user) # Eager load user who made the sale
    ).get_or_404(sale_id)
    # Accessing sale.items here (or in the template) will trigger the query
    return render_template('billing/sale_detail.html', title=f'Sale Details #{sale.id}', sale=sale)


# --- Process Sale Return Route ---
@billing_bp.route('/sales/return/<int:sale_id>', methods=['POST'])
@login_required
def process_return(sale_id):
    """Processes a return against an original sale."""
    original_sale = Sale.query.options(joinedload(Sale.items).joinedload(SaleItem.product)).get_or_404(sale_id)

    # --- Basic Checks ---
    # Check if a return already exists for this sale (prevent duplicate full returns)
    existing_return = SaleReturn.query.filter_by(original_sale_id=original_sale.id).first()
    if existing_return:
        flash(f'A return has already been processed for Sale ID {original_sale.id}. Cannot process another full return.', 'warning')
        return redirect(url_for('billing.view_sale', sale_id=sale_id))

    # For simplicity, this assumes a full return of all items at the price they were sold.
    # A more complex version would allow selecting items/quantities to return.
    reason = request.form.get('return_reason', 'Full return processed') # Get reason from form if provided
    total_refund = 0.0
    return_items_to_add = []
    stock_updates = []

    try:
        # Iterate through original sale items to create return items
        for item in original_sale.items:
            # Calculate amount refunded for this item (original net amount)
            amount_refunded_for_item = (item.quantity * item.price_at_sale) - item.discount_applied
            total_refund += amount_refunded_for_item

            # Create SaleReturnItem
            return_item = SaleReturnItem(
                product_id=item.product_id,
                quantity=item.quantity, # Returning the full original quantity
                amount_refunded=amount_refunded_for_item
                # sale_return_id will be set later
            )
            return_items_to_add.append(return_item)

            # Prepare stock update (increase stock)
            stock_updates.append({'product': item.product, 'quantity': item.quantity})

        # --- Create SaleReturn Record and Items in Transaction ---
        new_return = SaleReturn(
            return_timestamp=datetime.utcnow(),
            reason=reason,
            total_refunded_amount=total_refund,
            original_sale_id=original_sale.id,
            customer_id=original_sale.customer_id, # Link to the same customer
            processed_by_user_id=current_user.id # User processing the return
        )
        db.session.add(new_return)
        db.session.flush() # Get the new_return.id

        # Associate items with the return
        for ret_item in return_items_to_add:
            ret_item.sale_return_id = new_return.id
            db.session.add(ret_item)

        # Update stock quantities (increase)
        for update in stock_updates:
            # Need to ensure the product object is associated with the current session
            # Merging or re-fetching might be safer in complex scenarios
            product_to_update = db.session.merge(update['product'])
            product_to_update.stock_quantity += update['quantity']

        db.session.commit() # Commit all changes

        flash(f'Return for Sale ID {original_sale.id} processed successfully. Stock updated.', 'success')
        # Redirect back to the original sale detail page or a new return confirmation page
        return redirect(url_for('billing.view_sale', sale_id=sale_id))

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error processing return for Sale ID {sale_id}: {e}")
        flash(f'An error occurred while processing the return: {e}', 'danger')
        return redirect(url_for('billing.view_sale', sale_id=sale_id))