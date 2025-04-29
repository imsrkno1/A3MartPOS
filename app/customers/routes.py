# app/customers/routes.py
from flask import render_template, redirect, url_for, flash, request, current_app, jsonify
from flask_login import login_required, current_user
from sqlalchemy import or_

from . import customers_bp # Import the blueprint instance
from ..models import Customer # Import Customer model
from ..forms import CustomerForm # Import Customer form
from .. import db # Import the database instance

@customers_bp.route('/customers')
@login_required
def list_customers():
    """Displays a list of customers with search and pagination."""
    page = request.args.get('page', 1, type=int)
    query = request.args.get('query', '')

    customers_query = Customer.query.order_by(Customer.name.asc())

    # Apply search filter if query exists
    if query:
        search_term = f"%{query}%"
        customers_query = customers_query.filter(
            or_(
                Customer.name.ilike(search_term),
                Customer.phone_number.ilike(search_term),
                Customer.email.ilike(search_term)
            )
        )

    # Paginate the results
    pagination = customers_query.paginate(
        page=page, per_page=current_app.config.get('ITEMS_PER_PAGE', 15), error_out=False
    )
    customers = pagination.items

    return render_template(
        'customers/customers.html',
        title='Customers',
        customers=customers,
        pagination=pagination,
        query=query # Pass query back to template for search input persistence
    )

@customers_bp.route('/customers/add', methods=['GET', 'POST'])
@login_required
def add_customer():
    """Handles adding a new customer."""
    form = CustomerForm()
    if form.validate_on_submit():
        # Check for uniqueness if phone or email provided
        phone = form.phone_number.data
        email = form.email.data
        conflict = None
        if phone:
            conflict = Customer.query.filter_by(phone_number=phone).first()
        if not conflict and email:
             conflict = Customer.query.filter_by(email=email).first()

        if conflict:
             flash('A customer with this phone number or email already exists.', 'warning')
             return render_template('customers/customer_form.html', title='Add Customer', form=form, form_action='Add')

        new_customer = Customer(
            name=form.name.data,
            phone_number=phone,
            email=email,
            address=form.address.data
        )
        db.session.add(new_customer)
        try:
            db.session.commit()
            flash(f'Customer "{new_customer.name}" added successfully!', 'success')
            # Redirect to customer list or maybe back to billing if added from there?
            # For now, redirect to list.
            return redirect(url_for('customers.list_customers'))
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error adding customer: {e}")
            flash(f'Error adding customer. Please check logs.', 'danger')

    # If GET request or form validation failed
    return render_template('customers/customer_form.html', title='Add Customer', form=form, form_action='Add')

@customers_bp.route('/customers/edit/<int:customer_id>', methods=['GET', 'POST'])
@login_required
def edit_customer(customer_id):
    """Handles editing an existing customer."""
    customer = Customer.query.get_or_404(customer_id)
    form = CustomerForm(obj=customer) # Pre-populate form

    if form.validate_on_submit():
        # Check for uniqueness conflicts excluding self
        phone = form.phone_number.data
        email = form.email.data
        conflict = None

        if phone:
            conflict = Customer.query.filter(Customer.id != customer_id, Customer.phone_number == phone).first()
        if not conflict and email:
             conflict = Customer.query.filter(Customer.id != customer_id, Customer.email == email).first()

        if conflict:
             flash('Another customer with this phone number or email already exists.', 'warning')
             return render_template('customers/customer_form.html', title='Edit Customer', form=form, customer=customer, form_action='Edit')


        customer.name = form.name.data
        customer.phone_number = phone
        customer.email = email
        customer.address = form.address.data

        try:
            db.session.commit()
            flash(f'Customer "{customer.name}" updated successfully!', 'success')
            return redirect(url_for('customers.list_customers'))
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error updating customer: {e}")
            flash(f'Error updating customer. Please check logs.', 'danger')

    # If GET request or form validation failed
    return render_template('customers/customer_form.html', title='Edit Customer', form=form, customer=customer, form_action='Edit')


# --- Customer Search API (Helper for Billing form) ---
@customers_bp.route('/api/customers/search')
@login_required
def search_customers_api():
    """API endpoint to search customers for dynamic forms (e.g., billing)."""
    query = request.args.get('q', '')
    limit = request.args.get('limit', 10, type=int)

    if not query:
        return jsonify([])

    search_term = f"%{query}%"
    customers = Customer.query.filter(
        or_(
            Customer.name.ilike(search_term),
            Customer.phone_number.ilike(search_term),
            Customer.email.ilike(search_term)
        )
    ).limit(limit).all()

    # Format results for easy use in JavaScript
    results = [
        {
            'id': c.id,
            'text': f"{c.name} ({c.phone_number or c.email or 'No Contact'})", # Display text
            'name': c.name,
            'phone': c.phone_number,
            'email': c.email
        }
        for c in customers
    ]
    return jsonify(results)

# Add routes for deleting customers if needed