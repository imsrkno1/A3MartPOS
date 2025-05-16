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
    if query:
        search_term = f"%{query}%"
        customers_query = customers_query.filter(
            or_( Customer.name.ilike(search_term), Customer.phone_number.ilike(search_term), Customer.email.ilike(search_term) ))
    pagination = customers_query.paginate( page=page, per_page=current_app.config.get('ITEMS_PER_PAGE', 15), error_out=False )
    customers = pagination.items
    return render_template( 'customers/customers.html', title='Customers', customers=customers, pagination=pagination, query=query )

@customers_bp.route('/customers/add', methods=['GET', 'POST'])
@login_required
def add_customer():
    """Handles adding a new customer, with support for modal interaction."""
    form = CustomerForm()
    is_modal_context = request.args.get('context') == 'modal'

    if form.validate_on_submit():
        name = form.name.data
        phone = form.phone_number.data.strip() if form.phone_number.data else None
        # ** MODIFIED: Convert empty string email to None **
        email_data = form.email.data.strip() if form.email.data else None
        email = email_data if email_data else None # Ensure it's None if empty after strip

        address = form.address.data.strip() if form.address.data else None

        # Check for uniqueness if phone or email provided
        conflict = None
        if phone:
            conflict = Customer.query.filter_by(phone_number=phone).first()
        # ** MODIFIED: Only check email for uniqueness if it's not None **
        if not conflict and email: # 'email' here is now None or a non-empty string
             conflict = Customer.query.filter_by(email=email).first()

        if conflict:
             flash('A customer with this phone number or email already exists.', 'warning')
             if is_modal_context:
                 return render_template('customers/customer_form_content.html', form=form, form_action='Add', is_modal=True)
             else:
                 return render_template('customers/customer_form.html', title='Add Customer', form=form, form_action='Add')

        new_customer = Customer( name=name, phone_number=phone, email=email, address=address )
        db.session.add(new_customer)
        try:
            db.session.commit()
            flash(f'Customer "{new_customer.name}" added successfully!', 'success')

            if is_modal_context:
                return render_template('customers/modal_success_close.html',
                                       customer_id=new_customer.id,
                                       customer_name=new_customer.name,
                                       customer_phone=new_customer.phone_number,
                                       customer_email=new_customer.email)
            else:
                return redirect(url_for('customers.list_customers'))
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error adding customer: {e}")
            flash(f'Error adding customer. Please check logs.', 'danger')
            if is_modal_context:
                 return render_template('customers/customer_form_content.html', form=form, form_action='Add', is_modal=True)

    if is_modal_context:
        return render_template('customers/customer_form_content.html', form=form, form_action='Add', is_modal=True)
    else:
        return render_template('customers/customer_form.html', title='Add Customer', form=form, form_action='Add')


@customers_bp.route('/customers/edit/<int:customer_id>', methods=['GET', 'POST'])
@login_required
def edit_customer(customer_id):
    """Handles editing an existing customer."""
    customer = Customer.query.get_or_404(customer_id)
    form = CustomerForm(obj=customer) # Pre-populate form
    is_modal_context = request.args.get('context') == 'modal'

    if form.validate_on_submit():
        phone = form.phone_number.data.strip() if form.phone_number.data else None
        # ** MODIFIED: Convert empty string email to None **
        email_data = form.email.data.strip() if form.email.data else None
        email = email_data if email_data else None

        address = form.address.data.strip() if form.address.data else None

        # Check for uniqueness conflicts excluding self
        conflict = None
        if phone:
            conflict = Customer.query.filter(Customer.id != customer_id, Customer.phone_number == phone).first()
        # ** MODIFIED: Only check email for uniqueness if it's not None **
        if not conflict and email: # 'email' here is now None or a non-empty string
             conflict = Customer.query.filter(Customer.id != customer_id, Customer.email == email).first()

        if conflict:
             flash('Another customer with this phone number or email already exists.', 'warning')
             if is_modal_context:
                  return render_template('customers/customer_form_content.html', form=form, customer=customer, form_action='Edit', is_modal=True)
             else:
                  return render_template('customers/customer_form.html', title='Edit Customer', form=form, customer=customer, form_action='Edit')

        customer.name = form.name.data
        customer.phone_number = phone
        customer.email = email # Will be None if submitted as empty
        customer.address = address

        try:
            db.session.commit()
            flash(f'Customer "{customer.name}" updated successfully!', 'success')
            if is_modal_context:
                return render_template('customers/modal_success_close.html',
                                       customer_id=customer.id,
                                       customer_name=customer.name,
                                       customer_phone=customer.phone_number,
                                       customer_email=customer.email,
                                       refresh_parent=True) # Signal parent to refresh if needed
            else:
                return redirect(url_for('customers.list_customers'))
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error updating customer: {e}")
            flash(f'Error updating customer. Please check logs.', 'danger')
            if is_modal_context:
                return render_template('customers/customer_form_content.html', form=form, customer=customer, form_action='Edit', is_modal=True)

    if is_modal_context:
        return render_template('customers/customer_form_content.html', form=form, customer=customer, form_action='Edit', is_modal=True)
    else:
        return render_template('customers/customer_form.html', title='Edit Customer', form=form, customer=customer, form_action='Edit')


@customers_bp.route('/api/customers/search')
@login_required
def search_customers_api():
    query = request.args.get('q', ''); limit = request.args.get('limit', 10, type=int)
    if not query: return jsonify([])
    search_term = f"%{query}%"
    customers = Customer.query.filter( or_( Customer.name.ilike(search_term), Customer.phone_number.ilike(search_term), Customer.email.ilike(search_term) )).limit(limit).all()
    results = [ { 'id': c.id, 'text': f"{c.name} ({c.phone_number or c.email or 'No Contact'})", 'name': c.name, 'phone': c.phone_number, 'email': c.email } for c in customers ]
    return jsonify(results)
