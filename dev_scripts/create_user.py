import sys
import os

# Add the project directory to the system path to ensure app can be imported
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from models import User
from extensions import db

# Create an application instance
app = create_app()

# Define default user data
default_user_data = {
    "username": "admin",
    "email": "dev@microlumin.pt",
    "name": "Microlumin",
    "surname": "Admin",
    "avatar_image": "admin.png",
    "password": "factorylens",
    "role": "admin",
    "language": "en",
    "pin": "2020",
    "active": True
}

# This function will create the user
def create_user():
    # Ensure the app context is pushed for the database operations
    with app.app_context():
        # Check if the user already exists
        existing_user = User.query.filter_by(username=default_user_data["username"]).first()

        if existing_user:
            print(f"User '{default_user_data['username']}' already exists.")
            return

        # Create a new user instance
        new_user = User(
            username=default_user_data["username"],
            email=default_user_data["email"],
            name=default_user_data["name"],
            surname=default_user_data["surname"],
            avatar_image=default_user_data["avatar_image"],
            role=default_user_data["role"],
            language=default_user_data["language"],
            pin=default_user_data["pin"],
            active=default_user_data["active"]
        )
        
        # Set password (it will be hashed)
        new_user.set_password(default_user_data["password"])

        # Add to session and commit
        db.session.add(new_user)
        db.session.commit()

        print(f"User '{default_user_data['username']}' created successfully.")

# Run the function to create the user
if __name__ == "__main__":
    create_user()
