"""
WeatherWise — Development Entry Point
--------------------------------------
Run locally with:  python run.py
For production:    gunicorn wsgi:app
"""

import os

from app import create_app

# ── Create app using environment-specified config ─────────────
env = os.environ.get("FLASK_ENV", "development")
app = create_app(env)

if __name__ == "__main__":
    # Debug mode is driven by FLASK_ENV; never hardcode debug=True in prod
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        debug=(env == "development"),
    )
