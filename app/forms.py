# app/forms.py
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField, FloatField, IntegerField, TextAreaField, SelectField, HiddenField
from wtforms.validators import DataRequired, Length, Email, EqualTo, ValidationError, Optional, NumberRange, InputRequired

# Import models if needed for validation (e.g., checking if username exists)
from .models import User # Import User model

class LoginForm(FlaskForm):
    """Form for user login."""
    username = StringField('Username', validators=[DataRequired(), Length(min=4, max=64)])
    password = PasswordField('Password', validators=[DataRequired()])
    remember_me = BooleanField('Remember Me')
    submit = SubmitField('Sign In')

# --- NEW: Registration Form ---
class RegistrationForm(FlaskForm):
    """Form for user registration."""
    username = StringField('Username', validators=[DataRequired(), Length(min=4, max=64)])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('Confirm Password',
                                     validators=[DataRequired(), EqualTo('password', message='Passwords must match.')])
    submit = SubmitField('Register')

    def validate_username(self, username):
        """Validate if the username already exists."""
        user = User.query.filter_by(username=username.data).first()
        if user:
            raise ValidationError('That username is already taken. Please choose a different one.')


class ProductForm(FlaskForm):
    """Form for adding/editing products."""
    name = StringField('Product Name', validators=[DataRequired(), Length(max=128)])
    description = TextAreaField('Description', validators=[Optional(), Length(max=256)])
    barcode = StringField('Barcode', validators=[Optional(), Length(max=64)]) # Optional if auto-generating
    sku = StringField('SKU', validators=[Optional(), Length(max=64)])
    category = StringField('Category', validators=[Optional(), Length(max=64)])
    brand = StringField('Brand', validators=[Optional(), Length(max=64)])
    purchase_price = FloatField('Purchase Price', validators=[DataRequired(), NumberRange(min=0)])
    selling_price = FloatField('Selling Price', validators=[DataRequired(), NumberRange(min=0)])
    stock_quantity = IntegerField('Initial Stock Quantity', validators=[DataRequired(), NumberRange(min=0)], default=0)
    low_stock_threshold = IntegerField('Low Stock Threshold', validators=[Optional(), NumberRange(min=0)], default=10)
    discount_percent = FloatField('Discount (%)', validators=[Optional(), NumberRange(min=0, max=100)], default=0.0)
    submit = SubmitField('Save Product')


class CustomerForm(FlaskForm):
    """Form for adding/editing customers."""
    name = StringField('Customer Name', validators=[DataRequired(), Length(max=128)])
    phone_number = StringField('Phone Number', validators=[Optional(), Length(min=10, max=20)]) # Basic length validation
    email = StringField('Email', validators=[Optional(), Email(), Length(max=120)])
    address = TextAreaField('Address', validators=[Optional(), Length(max=256)])
    submit = SubmitField('Save Customer')


class PurchaseForm(FlaskForm):
    """Form for adding purchase entries (header info)."""
    supplier_name = StringField('Supplier Name', validators=[Optional(), Length(max=128)])
    invoice_number = StringField('Invoice Number', validators=[Optional(), Length(max=64)])
    notes = TextAreaField('Notes', validators=[Optional()])
    submit = SubmitField('Save Purchase')


class StockAdjustmentForm(FlaskForm):
    """Form for manually adjusting stock levels."""
    product_id = HiddenField('Product ID', validators=[DataRequired()])
    product_name = StringField('Product Name', render_kw={'readonly': True})
    current_stock = IntegerField('Current Stock', render_kw={'readonly': True})
    quantity_change = IntegerField('Quantity Change', validators=[InputRequired(message="Please enter quantity to add or remove.")])
    reason = SelectField('Reason', choices=[
        ('', '-- Select Reason --'), ('Stock Take', 'Stock Take'), ('Damage', 'Damage'),
        ('Theft', 'Theft'), ('Correction', 'Correction'), ('Initial Stock', 'Initial Stock'),
        ('Promotion/Demo', 'Promotion/Demo'), ('Other', 'Other')
    ], validators=[DataRequired(message="Please select a reason.")])
    notes = TextAreaField('Notes', validators=[Optional(), Length(max=500)])
    submit = SubmitField('Adjust Stock')

    def validate_quantity_change(form, field):
        if field.data == 0:
            raise ValidationError('Quantity change cannot be zero.')
