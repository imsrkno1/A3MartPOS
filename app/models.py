# app/models.py
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from . import db, login_manager

# --- Association Tables ---
class SaleItem(db.Model):
    __tablename__ = 'sale_items'
    id = db.Column(db.Integer, primary_key=True)
    sale_id = db.Column(db.Integer, db.ForeignKey('sales.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    price_at_sale = db.Column(db.Float, nullable=False)
    discount_applied = db.Column(db.Float, default=0.0)

class PurchaseItem(db.Model):
    __tablename__ = 'purchase_items'
    id = db.Column(db.Integer, primary_key=True)
    purchase_id = db.Column(db.Integer, db.ForeignKey('purchases.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    cost_price = db.Column(db.Float, nullable=False)

class SaleReturnItem(db.Model):
    __tablename__ = 'sale_return_items'
    id = db.Column(db.Integer, primary_key=True)
    sale_return_id = db.Column(db.Integer, db.ForeignKey('sale_returns.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    amount_refunded = db.Column(db.Float, nullable=False)

# --- Main Models ---
class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), index=True, unique=True, nullable=False)
    password_hash = db.Column(db.String(256))
    is_admin = db.Column(db.Boolean, default=False)
    last_login = db.Column(db.DateTime, default=datetime.utcnow)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    sales = db.relationship('Sale', backref='user', lazy='dynamic')
    purchases = db.relationship('Purchase', backref='user', lazy='dynamic')
    returns_processed = db.relationship('SaleReturn', backref='processed_by_user', lazy='dynamic')
    stock_adjustments = db.relationship('StockAdjustment', backref='adjusted_by_user', lazy='dynamic')
    def set_password(self, password): self.password_hash = generate_password_hash(password)
    def check_password(self, password): return check_password_hash(self.password_hash, password)
    def __repr__(self): return f'<User {self.username}>'

@login_manager.user_loader
def load_user(user_id): return User.query.get(int(user_id))

class Product(db.Model):
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
    # ** ADDED: Expiry Date field **
    expiry_date = db.Column(db.Date, nullable=True, index=True) # Assuming one expiry date per product listing for simplicity

    sale_items = db.relationship('SaleItem', backref='product', lazy='dynamic')
    purchase_items = db.relationship('PurchaseItem', backref='product', lazy='dynamic')
    return_items = db.relationship('SaleReturnItem', backref='product', lazy='dynamic')
    adjustments = db.relationship('StockAdjustment', backref='product', lazy='dynamic')
    def __repr__(self): return f'<Product {self.name} ({self.barcode})>'
    def is_low_stock(self): return self.stock_quantity <= self.low_stock_threshold

class Customer(db.Model):
    __tablename__ = 'customers'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False, index=True)
    phone_number = db.Column(db.String(20), unique=True, index=True, nullable=True)
    email = db.Column(db.String(120), unique=True, index=True, nullable=True)
    address = db.Column(db.String(256), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    sales = db.relationship('Sale', backref='customer', lazy='dynamic')
    returns = db.relationship('SaleReturn', backref='customer', lazy='dynamic')
    def __repr__(self): return f'<Customer {self.name} ({self.phone_number or self.email})>'

class Sale(db.Model):
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
    def __repr__(self): return f'<Sale ID: {self.id} Time: {self.sale_timestamp} Amount: {self.final_amount}>'

class Purchase(db.Model):
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
    def __repr__(self): return f'<Purchase ID: {self.id} Date: {self.purchase_date} Supplier: {self.supplier_name}>'

class SaleReturn(db.Model):
    __tablename__ = 'sale_returns'
    id = db.Column(db.Integer, primary_key=True)
    return_timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)
    reason = db.Column(db.String(255), nullable=True)
    total_refunded_amount = db.Column(db.Float, nullable=False)
    original_sale_id = db.Column(db.Integer, db.ForeignKey('sales.id'), nullable=False)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=True)
    processed_by_user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    items = db.relationship('SaleReturnItem', backref='sale_return', lazy='dynamic', cascade="all, delete-orphan")
    def __repr__(self): return f'<SaleReturn ID: {self.id} OriginalSaleID: {self.original_sale_id} Amount: {self.total_refunded_amount}>'

class StockAdjustment(db.Model):
    __tablename__ = 'stock_adjustments'
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)
    quantity_change = db.Column(db.Integer, nullable=False)
    reason = db.Column(db.String(255), nullable=False)
    notes = db.Column(db.Text, nullable=True)
    stock_level_before = db.Column(db.Integer, nullable=False)
    stock_level_after = db.Column(db.Integer, nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    def __repr__(self): change_type = '+' if self.quantity_change > 0 else ''; return f'<StockAdjustment ID: {self.id} ProductID: {self.product_id} Change: {change_type}{self.quantity_change}>'
