from flask import Flask
from config import Config
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config.from_object(Config)
db = SQLAlchemy(app)
app.secret_key = 'your_secret_key'

# Import after app is created to avoid circular imports
from .routes import init_scheduler
scheduler = init_scheduler(app)

from app import routes, models

with app.app_context():
    db.create_all()