# app/auth/routes.py
from flask import render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
# Updated import: Use urllib.parse instead of werkzeug.urls
from urllib.parse import urlparse, urljoin

from . import auth_bp # Import the blueprint instance from app/auth/__init__.py
from ..models import User # Import the User model
from ..forms import LoginForm # Import the LoginForm
from .. import db # Import the database instance

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Handles user login."""
    # Redirect if already logged in
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))

    form = LoginForm()
    # Process form submission
    if form.validate_on_submit():
        # Find user by username
        user = User.query.filter_by(username=form.username.data).first()

        # Validate user and password
        if user is None or not user.check_password(form.password.data):
            flash('Invalid username or password', 'danger')
            return redirect(url_for('auth.login')) # Redirect back to login on failure

        # Log user in
        login_user(user, remember=form.remember_me.data)
        flash(f'Welcome back, {user.username}!', 'success')

        # Update last login time (optional)
        try:
            user.last_login = db.func.now() # Use db.func for database functions
            db.session.commit()
        except Exception as e:
            # Log error if update fails, but don't block login
            current_app.logger.error(f"Error updating last_login for user {user.username}: {e}")
            db.session.rollback() # Rollback the specific change

        # --- Redirect Logic Updated ---
        next_page = request.args.get('next')
        # Security check: ensure next_page is a relative path within our site
        if not next_page or urlparse(next_page).netloc != '':
            next_page = url_for('main.dashboard') # Default redirect to dashboard

        return redirect(next_page)
        # --- End of Update ---

    # Render login page for GET request or failed validation
    return render_template('auth/login.html', title='Sign In', form=form)


@auth_bp.route('/logout')
@login_required # Ensure user is logged in to access logout
def logout():
    """Handles user logout."""
    logout_user() # Log the user out
    flash('You have been logged out.', 'info') # Inform user
    return redirect(url_for('auth.login')) # Redirect to login page