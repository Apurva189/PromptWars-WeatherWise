"""
WeatherWise — WSGI Entry Point
--------------------------------
Used by Gunicorn in production:
    gunicorn wsgi:app --workers 4 --bind 0.0.0.0:$PORT

Render / Railway / Cloud Run all look for this file.
"""

from app import create_app

app = create_app("production")
