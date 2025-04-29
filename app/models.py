# app/models.py
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from . import db, login_manager # Import db and login_manager from app/__init__.py

# --- Association Tables (for Many-to-Many relationships) ---

# Association table for Sales and Products (SaleItems)
# This table stores the details of each product within a specific sale,
# including quantity and price at the time of sale.
class SaleItem(db.Model):
    __tablename__ = 'sale_items'
    id = db.Column(db.Integer, primary_key=True)
    sale_id = db.Column(db.Integer, db.ForeignKey('sales.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    price_at_sale = db.Column(db.Float, nullable=False) # Price per unit at time of sale
    discount_applied = db.Column(db.Float, default=0.0) # Discount amount for this item in the sale

    # Relationships (optional but can be helpful for querying)
    # sale = db.relationship('Sale', back_populates='items') # Defined in Sale model
    # product = db.relationship('Product') # Defined below


# --- Main Models ---

class User(UserMixin, db.Model):
    """User model for authentication."""
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), index=True, unique=True, nullable=False)
    password_hash = db.Column(db.String(256)) # Increased length for stronger hashes
    is_admin = db.Column(db.Boolean, default=False)
    last_login = db.Column(db.DateTime, default=datetime.utcnow)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        """Hashes the password."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Checks if the provided password matches the hash."""
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.username}>'

# Flask-Login user loader callback
@login_manager.user_loader
def load_user(user_id):
    """Loads user object for Flask-Login."""
    return User.query.get(int(user_id))


class Product(db.Model):
    """Product model for items in inventory."""
    __tablename__ = 'products'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False, index=True)
    description = db.Column(db.String(256))
    barcode = db.Column(db.String(64), unique=True, index=True) # Can be manually entered or generated
    sku = db.Column(db.String(64), unique=True, index=True, nullable=True) # Stock Keeping Unit
    category = db.Column(db.String(64), index=True)
    brand = db.Column(db.String(64), index=True, nullable=True)
    purchase_price = db.Column(db.Float, nullable=False, default=0.0) # Cost price
    selling_price = db.Column(db.Float, nullable=False) # MRP or selling price
    stock_quantity = db.Column(db.Integer, default=0)
    low_stock_threshold = db.Column(db.Integer, default=10) # Product specific threshold
    discount_percent = db.Column(db.Float, default=0.0) # Default discount for this product
    is_active = db.Column(db.Boolean, default=True) # To deactivate products without deleting
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship to SaleItem (One-to-Many: One Product can be in many SaleItems)
    sale_items = db.relationship('SaleItem', backref='product', lazy='dynamic')
    # Relationship to PurchaseItem (One-to-Many: One Product can be in many PurchaseItems)
    purchase_items = db.relationship('PurchaseItem', backref='product', lazy='dynamic')

    def __repr__(self):
        return f'<Product {self.name} ({self.barcode})>'

    def is_low_stock(self):
        """Checks if the product quantity is below its threshold."""
        return self.stock_quantity <= self.low_stock_threshold


class Customer(db.Model):
    """Customer model."""
    __tablename__ = 'customers'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False, index=True)
    phone_number = db.Column(db.String(20), unique=True, index=True, nullable=True)
    email = db.Column(db.String(120), unique=True, index=True, nullable=True)
    address = db.Column(db.String(256), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationship to Sales (One-to-Many: One Customer can have many Sales)
    sales = db.relationship('Sale', backref='customer', lazy='dynamic')

    def __repr__(self):
        return f'<Customer {self.name} ({self.phone_number or self.email})>'


class Sale(db.Model):
    """Sale transaction model."""
    __tablename__ = 'sales'
    id = db.Column(db.Integer, primary_key=True)
    sale_timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)
    total_amount = db.Column(db.Float, nullable=False)
    discount_total = db.Column(db.Float, default=0.0) # Total discount applied to the sale
    final_amount = db.Column(db.Float, nullable=False) # total_amount - discount_total
    payment_method = db.Column(db.String(50), default='Cash') # e.g., Cash, Card, UPI
    notes = db.Column(db.Text, nullable=True)

    # Foreign Keys
    user_id = db.Column(db.Integer, db.ForeignKey('users.id')) # User who made the sale
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=True) # Optional customer

    # Relationship to SaleItem (One-to-Many: One Sale has many SaleItems)
    # cascade="all, delete-orphan": ensures sale items are deleted if the sale is deleted
    items = db.relationship('SaleItem', backref='sale', lazy='dynamic', cascade="all, delete-orphan")

    # Relationship back to User (Many-to-One)
    user = db.relationship('User', backref=db.backref('sales', lazy='dynamic'))
    # Relationship back to Customer defined in Customer model via backref='customer'

    def __repr__(self):
        return f'<Sale ID: {self.id} Time: {self.sale_timestamp} Amount: {self.final_amount}>'


class Purchase(db.Model):
    """Purchase/Stock entry model."""
    __tablename__ = 'purchases'
    id = db.Column(db.Integer, primary_key=True)
    purchase_date = db.Column(db.DateTime, index=True, default=datetime.utcnow)
    supplier_name = db.Column(db.String(128), nullable=True)
    invoice_number = db.Column(db.String(64), nullable=True)
    total_cost = db.Column(db.Float, nullable=False)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Foreign Key
    user_id = db.Column(db.Integer, db.ForeignKey('users.id')) # User who entered the purchase

    # Relationship to PurchaseItem (One-to-Many: One Purchase has many PurchaseItems)
    items = db.relationship('PurchaseItem', backref='purchase', lazy='dynamic', cascade="all, delete-orphan")

    # Relationship back to User
    user = db.relationship('User', backref=db.backref('purchases', lazy='dynamic'))

    def __repr__(self):
        return f'<Purchase ID: {self.id} Date: {self.purchase_date} Supplier: {self.supplier_name}>'


class PurchaseItem(db.Model):
    """Details of items within a specific purchase."""
    __tablename__ = 'purchase_items'
    id = db.Column(db.Integer, primary_key=True)
    purchase_id = db.Column(db.Integer, db.ForeignKey('purchases.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    cost_price = db.Column(db.Float, nullable=False) # Cost per unit for this purchase

    # Relationships defined via backref in Product and Purchase models

    def __repr__(self):
        return f'<PurchaseItem PurchaseID: {self.purchase_id} ProductID: {self.product_id} Qty: {self.quantity}>'

# --- Optional: Settings Table ---
# Could be used for storing application-wide settings if needed later
# class Setting(db.Model):
#     __tablename__ = 'settings'
#     id = db.Column(db.Integer, primary_key=True)
#     key = db.Column(db.String(64), unique=True, nullable=False)
#     value = db.Column(db.String(256))
#     description = db.Column(db.String(256))