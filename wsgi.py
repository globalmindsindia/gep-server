# wsgi.py
"""
WSGI entry point for local development.
This loads your Flask app from app.py using the create_app() factory.
"""

from app import create_app

# WSGI callable that servers expect
application = create_app()

# Optional alias so you can run "python wsgi.py" directly
app = application

if __name__ == "__main__":
    # Local development server
    app.run(host="127.0.0.1", port=8000, debug=True)
