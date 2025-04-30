# app/models.py
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from . import db, login_manager # Import db and login_manager from app/__init__.py

# --- Association Tables (for Many-to-Many relationships) ---

class SaleItem(db.Model):
    __tablename__ = 'sale_items'
    id = db.Column(db.Integer, primary_key=True)
    sale_id = db.Column(db.Integer, db.ForeignKey('sales.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    price_at_sale = db.Column(db.Float, nullable=False) # Price per unit at time of sale
    discount_applied = db.Column(db.Float, default=0.0) # Discount amount for this item in the sale

class PurchaseItem(db.Model):
    """Details of items within a specific purchase."""
    __tablename__ = 'purchase_items'
    id = db.Column(db.Integer, primary_key=True)
    purchase_id = db.Column(db.Integer, db.ForeignKey('purchases.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    cost_price = db.Column(db.Float, nullable=False) # Cost per unit for this purchase

    def __repr__(self):
        return f'<PurchaseItem PurchaseID: {self.purchase_id} ProductID: {self.product_id} Qty: {self.quantity}>'

class SaleReturnItem(db.Model):
    """Details of items within a specific return transaction."""
    __tablename__ = 'sale_return_items'
    id = db.Column(db.Integer, primary_key=True)
    sale_return_id = db.Column(db.Integer, db.ForeignKey('sale_returns.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False) # Quantity returned
    amount_refunded = db.Column(db.Float, nullable=False) # Amount refunded for this specific item line

    def __repr__(self):
        return f'<SaleReturnItem ReturnID: {self.sale_return_id} ProductID: {self.product_id} Qty: {self.quantity}>'


# --- Main Models ---

class User(UserMixin, db.Model):
    """User model for authentication."""
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), index=True, unique=True, nullable=False)
    password_hash = db.Column(db.String(256))
    is_admin = db.Column(db.Boolean, default=False)
    last_login = db.Column(db.DateTime, default=datetime.utcnow)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    sales = db.relationship('Sale', backref='user', lazy='dynamic') # User who processed sale
    purchases = db.relationship('Purchase', backref='user', lazy='dynamic') # User who entered purchase
    returns_processed = db.relationship('SaleReturn', backref='processed_by_user', lazy='dynamic') # User who processed return
    stock_adjustments = db.relationship('StockAdjustment', backref='adjusted_by_user', lazy='dynamic') # User who made adjustment

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.username}>'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


class Product(db.Model):
    """Product model for items in inventory."""
    __tablename__ = 'products'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False, index=True)
    description = db.Column(db.String(256))
    barcode = db.Column(db.String(64), unique=True, index=True)
    sku = db.Column(db.String(64), unique=True, index=True, nullable=True)
    category = db.Column(db.String(64), index=True)
    brand = db.Column(db.String(64), index=True, nullable=True)
    purchase_price = db.Column(db.Float, nullable=False, default=0.0)
    selling_price = db.Column(db.Float, nullable=False)
    stock_quantity = db.Column(db.Integer, default=0)
    low_stock_threshold = db.Column(db.Integer, default=10)
    discount_percent = db.Column(db.Float, default=0.0)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    sale_items = db.relationship('SaleItem', backref='product', lazy='dynamic')
    purchase_items = db.relationship('PurchaseItem', backref='product', lazy='dynamic')
    return_items = db.relationship('SaleReturnItem', backref='product', lazy='dynamic')
    adjustments = db.relationship('StockAdjustment', backref='product', lazy='dynamic') # Link to adjustments

    def __repr__(self):
        return f'<Product {self.name} ({self.barcode})>'

    def is_low_stock(self):
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

    sales = db.relationship('Sale', backref='customer', lazy='dynamic')
    returns = db.relationship('SaleReturn', backref='customer', lazy='dynamic')

    def __repr__(self):
        return f'<Customer {self.name} ({self.phone_number or self.email})>'


class Sale(db.Model):
    """Sale transaction model."""
    __tablename__ = 'sales'
    id = db.Column(db.Integer, primary_key=True)
    sale_timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)
    total_amount = db.Column(db.Float, nullable=False)
    discount_total = db.Column(db.Float, default=0.0)
    final_amount = db.Column(db.Float, nullable=False)
    payment_method = db.Column(db.String(50), default='Cash')
    notes = db.Column(db.Text, nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=True)
    items = db.relationship('SaleItem', backref='sale', lazy='dynamic', cascade="all, delete-orphan")
    returns = db.relationship('SaleReturn', backref='original_sale', lazy='dynamic')

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
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    items = db.relationship('PurchaseItem', backref='purchase', lazy='dynamic', cascade="all, delete-orphan")

    def __repr__(self):
        return f'<Purchase ID: {self.id} Date: {self.purchase_date} Supplier: {self.supplier_name}>'


class SaleReturn(db.Model):
    """Represents a return transaction."""
    __tablename__ = 'sale_returns'
    id = db.Column(db.Integer, primary_key=True)
    return_timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)
    reason = db.Column(db.String(255), nullable=True)
    total_refunded_amount = db.Column(db.Float, nullable=False)
    original_sale_id = db.Column(db.Integer, db.ForeignKey('sales.id'), nullable=False)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=True)
    processed_by_user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    items = db.relationship('SaleReturnItem', backref='sale_return', lazy='dynamic', cascade="all, delete-orphan")

    def __repr__(self):
        return f'<SaleReturn ID: {self.id} OriginalSaleID: {self.original_sale_id} Amount: {self.total_refunded_amount}>'


# --- NEW: Stock Adjustment Model ---

class StockAdjustment(db.Model):
    """Records manual adjustments to stock levels."""
    __tablename__ = 'stock_adjustments'
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)
    quantity_change = db.Column(db.Integer, nullable=False) # Positive for increase, negative for decrease
    reason = db.Column(db.String(255), nullable=False) # e.g., Stock Take, Damage, Correction, Initial
    notes = db.Column(db.Text, nullable=True) # Optional further details
    stock_level_before = db.Column(db.Integer, nullable=False) # Stock level before this adjustment
    stock_level_after = db.Column(db.Integer, nullable=False) # Stock level after this adjustment

    # Foreign Keys
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False) # User making adjustment

    # Relationships defined via backref in Product and User models

    def __repr__(self):
        change_type = '+' if self.quantity_change > 0 else ''
        return f'<StockAdjustment ID: {self.id} ProductID: {self.product_id} Change: {change_type}{self.quantity_change}>'