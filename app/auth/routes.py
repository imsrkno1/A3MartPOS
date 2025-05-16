# app/auth/routes.py
from flask import render_template, redirect, url_for, flash, request, current_app
from flask_login import login_user, logout_user, login_required, current_user
from urllib.parse import urlparse, urljoin

from . import auth_bp
from ..models import User
from ..forms import LoginForm, RegistrationForm # Import RegistrationForm
from .. import db

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Handles user login."""
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user is None or not user.check_password(form.password.data):
            flash('Invalid username or password', 'danger')
            return redirect(url_for('auth.login'))
        login_user(user, remember=form.remember_me.data)
        try:
            user.last_login = db.func.now()
            db.session.commit()
        except Exception as e:
            current_app.logger.error(f"Error updating last_login for user {user.username}: {e}")
            db.session.rollback()
        next_page = request.args.get('next')
        if not next_page or urlparse(next_page).netloc != '':
            next_page = url_for('main.dashboard')
        return redirect(next_page)
    return render_template('auth/login.html', title='Sign In', form=form)


@auth_bp.route('/logout')
@login_required
def logout():
    """Handles user logout."""
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))

# --- NEW: Registration Route ---
@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """Handles user registration. The first registered user becomes an admin."""
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard')) # Redirect if already logged in

    form = RegistrationForm()
    if form.validate_on_submit():
        # Check if any admin user already exists
        admin_exists = User.query.filter_by(is_admin=True).first()
        is_first_admin = not admin_exists # This new user will be the first admin

        new_user = User(username=form.username.data, is_admin=is_first_admin)
        new_user.set_password(form.password.data)
        db.session.add(new_user)
        try:
            db.session.commit()
            if is_first_admin:
                flash(f'Congratulations! Admin account "{new_user.username}" registered successfully. Please log in.', 'success')
            else:
                flash(f'Account "{new_user.username}" registered successfully. Please log in.', 'success')
            return redirect(url_for('auth.login'))
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error during registration: {e}")
            flash('An error occurred during registration. Please try again.', 'danger')

    return render_template('auth/register.html', title='Register', form=form)
