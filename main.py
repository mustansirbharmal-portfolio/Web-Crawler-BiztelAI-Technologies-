# Import the app from flask_app.py
from flask_app import app

# This file is now just a simple module that imports the Flask app
# and makes it available for Gunicorn to use

if __name__ == "__main__":
    # If we're running this file directly, start the Flask development server
    app.run(host="0.0.0.0", port=5000, debug=True)
