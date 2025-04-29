# app/forms.py
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField, FloatField, IntegerField, TextAreaField, SelectField
from wtforms.validators import DataRequired, Length, Email, EqualTo, ValidationError, Optional, NumberRange

# Import models if needed for validation (e.g., checking if username exists)
# from .models import User

class LoginForm(FlaskForm):
    """Form for user login."""
    username = StringField('Username', validators=[DataRequired(), Length(min=4, max=64)])
    password = PasswordField('Password', validators=[DataRequired()])
    remember_me = BooleanField('Remember Me')
    submit = SubmitField('Sign In')

# --- Placeholder Forms for other features (We will fill these in later) ---

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

    # Add custom validators if needed, e.g., check if barcode/SKU is unique

class CustomerForm(FlaskForm):
    """Form for adding/editing customers."""
    name = StringField('Customer Name', validators=[DataRequired(), Length(max=128)])
    phone_number = StringField('Phone Number', validators=[Optional(), Length(min=10, max=20)]) # Basic length validation
    email = StringField('Email', validators=[Optional(), Email(), Length(max=120)])
    address = TextAreaField('Address', validators=[Optional(), Length(max=256)])
    submit = SubmitField('Save Customer')

    # Add custom validators, e.g., check if phone/email is unique if required

class PurchaseForm(FlaskForm):
    """Form for adding purchase entries (header info)."""
    supplier_name = StringField('Supplier Name', validators=[Optional(), Length(max=128)])
    invoice_number = StringField('Invoice Number', validators=[Optional(), Length(max=64)])
    # Purchase items will likely be handled dynamically with JavaScript on the frontend
    notes = TextAreaField('Notes', validators=[Optional()])
    submit = SubmitField('Save Purchase') # Might be handled differently depending on UI flow

# Add other forms as needed (e.g., User management, Settings)