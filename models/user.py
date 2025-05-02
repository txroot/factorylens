# models/user.py
from flask_login import UserMixin
from extensions import db
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

# ----------------------------------------------------------------------
# 'User' model to store user data
# ----------------------------------------------------------------------

class User(db.Model, UserMixin):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    name = db.Column(db.String(80), nullable=False)       # First name
    surname = db.Column(db.String(80), nullable=False)      # Surname/Last name
    avatar_image = db.Column(db.String(255), nullable=True)
    password = db.Column(db.String(255), nullable=False)    # Hashed password
    role = db.Column(db.String(20), nullable=False)         # e.g. "admin", "sales", "warehouse", "buyer", "guest"
    language = db.Column(db.String(10), nullable=False, default='en')
    recovery_token = db.Column(db.String(255), nullable=True)
    pin = db.Column(db.String(10), nullable=True)           # PIN code for additional authentication
    active = db.Column(db.Boolean, nullable=False, default=True)  # Database-backed active flag
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
     
    def __repr__(self):
        return f'<User {self.username}>'
    
    @property
    def is_active(self):
        """Return whether the user is active, as stored in the database."""
        return self.active
        
    @property
    def fullname(self):
        """Returns the full name, composed of first name and surname."""
        return f"{self.name} {self.surname}"

    def set_password(self, password_plaintext):
        """Hashes the plaintext password and stores it."""
        self.password = generate_password_hash(password_plaintext)
    
    def check_password(self, password_plaintext):
        """Verifies that the plaintext password matches the stored hash."""
        return check_password_hash(self.password, password_plaintext)
