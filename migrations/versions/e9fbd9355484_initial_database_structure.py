"""Initial database structure

Revision ID: e9fbd9355484
Revises: 
Create Date: 2025-04-29 19:01:40.657989

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e9fbd9355484'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('customers',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=128), nullable=False),
    sa.Column('phone_number', sa.String(length=20), nullable=True),
    sa.Column('email', sa.String(length=120), nullable=True),
    sa.Column('address', sa.String(length=256), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('customers', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_customers_email'), ['email'], unique=True)
        batch_op.create_index(batch_op.f('ix_customers_name'), ['name'], unique=False)
        batch_op.create_index(batch_op.f('ix_customers_phone_number'), ['phone_number'], unique=True)

    op.create_table('products',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=128), nullable=False),
    sa.Column('description', sa.String(length=256), nullable=True),
    sa.Column('barcode', sa.String(length=64), nullable=True),
    sa.Column('sku', sa.String(length=64), nullable=True),
    sa.Column('category', sa.String(length=64), nullable=True),
    sa.Column('brand', sa.String(length=64), nullable=True),
    sa.Column('purchase_price', sa.Float(), nullable=False),
    sa.Column('selling_price', sa.Float(), nullable=False),
    sa.Column('stock_quantity', sa.Integer(), nullable=True),
    sa.Column('low_stock_threshold', sa.Integer(), nullable=True),
    sa.Column('discount_percent', sa.Float(), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('products', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_products_barcode'), ['barcode'], unique=True)
        batch_op.create_index(batch_op.f('ix_products_brand'), ['brand'], unique=False)
        batch_op.create_index(batch_op.f('ix_products_category'), ['category'], unique=False)
        batch_op.create_index(batch_op.f('ix_products_name'), ['name'], unique=False)
        batch_op.create_index(batch_op.f('ix_products_sku'), ['sku'], unique=True)

    op.create_table('users',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('username', sa.String(length=64), nullable=False),
    sa.Column('password_hash', sa.String(length=256), nullable=True),
    sa.Column('is_admin', sa.Boolean(), nullable=True),
    sa.Column('last_login', sa.DateTime(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_users_username'), ['username'], unique=True)

    op.create_table('purchases',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('purchase_date', sa.DateTime(), nullable=True),
    sa.Column('supplier_name', sa.String(length=128), nullable=True),
    sa.Column('invoice_number', sa.String(length=64), nullable=True),
    sa.Column('total_cost', sa.Float(), nullable=False),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('user_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('purchases', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_purchases_purchase_date'), ['purchase_date'], unique=False)

    op.create_table('sales',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('sale_timestamp', sa.DateTime(), nullable=True),
    sa.Column('total_amount', sa.Float(), nullable=False),
    sa.Column('discount_total', sa.Float(), nullable=True),
    sa.Column('final_amount', sa.Float(), nullable=False),
    sa.Column('payment_method', sa.String(length=50), nullable=True),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('user_id', sa.Integer(), nullable=True),
    sa.Column('customer_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('sales', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_sales_sale_timestamp'), ['sale_timestamp'], unique=False)

    op.create_table('purchase_items',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('purchase_id', sa.Integer(), nullable=False),
    sa.Column('product_id', sa.Integer(), nullable=False),
    sa.Column('quantity', sa.Integer(), nullable=False),
    sa.Column('cost_price', sa.Float(), nullable=False),
    sa.ForeignKeyConstraint(['product_id'], ['products.id'], ),
    sa.ForeignKeyConstraint(['purchase_id'], ['purchases.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('sale_items',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('sale_id', sa.Integer(), nullable=False),
    sa.Column('product_id', sa.Integer(), nullable=False),
    sa.Column('quantity', sa.Integer(), nullable=False),
    sa.Column('price_at_sale', sa.Float(), nullable=False),
    sa.Column('discount_applied', sa.Float(), nullable=True),
    sa.ForeignKeyConstraint(['product_id'], ['products.id'], ),
    sa.ForeignKeyConstraint(['sale_id'], ['sales.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('sale_items')
    op.drop_table('purchase_items')
    with op.batch_alter_table('sales', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_sales_sale_timestamp'))

    op.drop_table('sales')
    with op.batch_alter_table('purchases', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_purchases_purchase_date'))

    op.drop_table('purchases')
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_users_username'))

    op.drop_table('users')
    with op.batch_alter_table('products', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_products_sku'))
        batch_op.drop_index(batch_op.f('ix_products_name'))
        batch_op.drop_index(batch_op.f('ix_products_category'))
        batch_op.drop_index(batch_op.f('ix_products_brand'))
        batch_op.drop_index(batch_op.f('ix_products_barcode'))

    op.drop_table('products')
    with op.batch_alter_table('customers', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_customers_phone_number'))
        batch_op.drop_index(batch_op.f('ix_customers_name'))
        batch_op.drop_index(batch_op.f('ix_customers_email'))

    op.drop_table('customers')
    # ### end Alembic commands ###
