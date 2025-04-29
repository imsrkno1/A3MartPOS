# run.py
import os
import click # Import click for CLI commands
from app import create_app, db
# Import all models to ensure they are known to Flask-Migrate and the shell
from app.models import User, Product, Customer, Sale, SaleItem, Purchase, PurchaseItem
from flask_migrate import Migrate

# Determine the configuration name (e.g., 'development', 'production')
# Default to 'development' if FLASK_CONFIG is not set
config_name = os.getenv('FLASK_CONFIG') or 'default'
app = create_app(config_name)
migrate = Migrate(app, db) # Initialize Flask-Migrate

# Create an application shell context for Flask CLI
@app.shell_context_processor
def make_shell_context():
    """Makes variables available in the Flask shell."""
    # Include all models in the shell context for easy access
    return dict(db=db, User=User, Product=Product, Customer=Customer,
                Sale=Sale, SaleItem=SaleItem, Purchase=Purchase, PurchaseItem=PurchaseItem)

# Custom CLI commands (Example: create admin user)
@app.cli.command('create-admin')
@click.argument('username')
@click.argument('password')
def create_admin(username, password):
    """Creates the initial admin user."""
    from app.models import User # Import inside function to avoid circular dependency issues
    if User.query.filter_by(username=username).first():
        print(f'User {username} already exists.')
        return
    admin = User(username=username, is_admin=True)
    admin.set_password(password)
    db.session.add(admin)
    db.session.commit()
    print(f'Admin user {username} created successfully.')

# Add more CLI commands as needed, e.g., for seeding data

if __name__ == '__main__':
    # Note: For production, use a WSGI server like Gunicorn, not app.run()
    # Example: gunicorn --bind 0.0.0.0:5000 run:app
    # The host='0.0.0.0' makes the server accessible on your network (useful for Codespaces/VMs)
    app.run(debug=app.config['DEBUG'], host='0.0.0.0', port=5000)