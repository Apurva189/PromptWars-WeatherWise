# 🌧️ WeatherWise — AI-Powered Monsoon Preparedness

> **GenAI-powered citizen safety assistant for India's monsoon season**  
> Personalised plans · Emergency checklists · Travel advisories · Real-time alerts · Multilingual

[![Python](https://img.shields.io/badge/Python-3.10+-blue)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-3.0-green)](https://flask.palletsprojects.com)
[![Gemini AI](https://img.shields.io/badge/Gemini-1.5_Flash-orange)](https://aistudio.google.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)

---

## 📋 Table of Contents

1. [Features](#-features)
2. [Architecture](#-architecture)
3. [Prerequisites](#-prerequisites)
4. [Local Setup](#-local-setup)
5. [Running Locally](#-running-locally)
6. [Running Tests](#-running-tests)
7. [Deployment](#-deployment)
   - [Render (Recommended)](#render-recommended-free)
   - [Railway](#railway)
   - [Google Cloud Run](#google-cloud-run)
8. [API Reference](#-api-reference)
9. [Security](#-security)
10. [Project Structure](#-project-structure)

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| 💬 **AI Chat** | Conversational monsoon safety assistant — ask anything, get instant guidance |
| 📋 **Personalised Plans** | Location + family profile–specific preparedness plans for pre/during/post monsoon |
| ✅ **Emergency Checklists** | Priority-categorised 72-hour kits, home waterproofing, and more |
| 🚗 **Travel Advisories** | Route risk assessment, go/no-go decisions, and transport-specific guidance |
| ⚠️ **Safety Alerts** | Red/Orange/Yellow/Green colour-coded alerts based on live weather + AI analysis |
| 🌐 **Multilingual** | Responds in 12 Indian languages (Hindi, Tamil, Bengali, Telugu, Marathi, and more) |
| 📡 **Live Weather** | Real-time weather from Open-Meteo (free, no extra API key needed) |

---

## 🏗️ Architecture

```
WeatherWise
├── Flask Backend (Python)
│   ├── Routes:   Page routes (/) + API endpoints (/api/*)
│   ├── Services: GeminiService (AI) + WeatherService (Open-Meteo)
│   └── Utils:    Input validators & sanitisers
├── Frontend (Vanilla HTML/CSS/JS)
│   ├── Landing page with animated rain hero
│   └── Dashboard with 5 tabbed AI feature panels
└── AI Layer (Google Gemini 1.5 Flash)
    ├── System instruction: Monsoon safety expert persona
    ├── Weather-grounded prompts (live data injected)
    └── Structured prompt engineering per feature
```

**Key design choices:**
- **No database** — chat history stored in server-side Flask sessions
- **No extra API keys** — Open-Meteo weather is 100% free
- **Rate limiting** — 10 AI calls/minute per IP (protects your Gemini quota)
- **Security headers** — CSP, X-Frame-Options, HSTS configured by default

---

## 🔧 Prerequisites

- **Python 3.10+** — [download](https://python.org/downloads)
- **Google Gemini API key** — [get a free key](https://aistudio.google.com/app/apikey)
- **Git** — for cloning and deployment

---

## 💻 Local Setup

### 1. Clone the repository

```bash
git clone https://github.com/YOUR_USERNAME/PromptWars-WeatherWise.git
cd PromptWars-WeatherWise
```

### 2. Create and activate a virtual environment

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS / Linux
python3 -m venv venv
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

```bash
# Copy the template
cp .env.example .env
```

Open `.env` and fill in your values:

```env
# Required
GEMINI_API_KEY=your_gemini_api_key_here

# Optional (defaults shown)
GEMINI_MODEL=gemini-3.5-flash
SECRET_KEY=your_long_random_secret_key
FLASK_ENV=development
```

> ⚠️ **Never commit `.env` to version control.** It is already in `.gitignore`.

### 5. Generate a secure SECRET_KEY

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

Paste the output as your `SECRET_KEY` in `.env`.

---

## 🚀 Running Locally

```bash
# With virtual environment activated
python run.py
```

Then open your browser at: **http://localhost:5000**

You should see:
- Landing page at `http://localhost:5000/`
- Dashboard at `http://localhost:5000/dashboard`
- Health check at `http://localhost:5000/health`

### Verifying everything works

1. **Landing page** — Opens with animated rain effect and feature cards
2. **Weather widget** — Type "Mumbai" and press 🔍 — live weather should load
3. **Chat tab** — Ask "What should I do during a flood?"
4. **Plan tab** — Enter a city, set family size, click Generate
5. **Checklist tab** — Enter city + housing type, generate checklist
6. **Travel tab** — Enter origin/destination/date, get advisory
7. **Alerts tab** — Enter city + phase, generate colour-coded alerts
8. **Language** — Change language to "Hindi" and try any feature

---

## 🧪 Running Tests

```bash
# Run all tests with verbose output
pytest tests/ -v

# Run with short traceback for CI
pytest tests/ -v --tb=short

# Run a specific test file
pytest tests/test_validators.py -v
pytest tests/test_services.py -v
pytest tests/test_routes.py -v

# Run a specific test class
pytest tests/test_validators.py::TestSanitiseText -v

# Run with coverage report (install pytest-cov first)
pip install pytest-cov
pytest tests/ --cov=app --cov-report=term-missing
```

**Test structure:**
| File | What it tests |
|------|---------------|
| `test_validators.py` | All input validators (XSS, boundaries, type checks) |
| `test_services.py` | GeminiService + WeatherService (mocked API calls) |
| `test_routes.py` | All HTTP endpoints (integration tests with mock AI) |

---

## 🌐 Deployment

### Render (Recommended — Free)

Render offers a free tier with automatic HTTPS and GitHub integration.

#### Step 1: Push code to GitHub

```bash
git add .
git commit -m "feat: initial WeatherWise application"
git push origin main
```

#### Step 2: Create a Render Web Service

1. Go to [render.com](https://render.com) → **New** → **Web Service**
2. Connect your GitHub repository
3. Configure:
   - **Name:** `weatherwise`
   - **Runtime:** `Python 3`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn wsgi:app --workers 2 --threads 2 --bind 0.0.0.0:$PORT --timeout 120`

#### Step 3: Set Environment Variables in Render

In **Environment** → **Add Environment Variables:**

| Key | Value |
|-----|-------|
| `GEMINI_API_KEY` | Your Gemini API key |
| `SECRET_KEY` | Long random string |
| `GEMINI_MODEL` | `gemini-3.5-flash` |
| `FLASK_ENV` | `production` |

#### Step 4: Deploy

Click **Deploy Web Service**. Render will build and deploy automatically.

#### Step 5: Verify Deployment

```bash
# Health check
curl https://your-app.onrender.com/health

# Expected response:
# {"service": "WeatherWise", "status": "ok"}
```

Then open `https://your-app.onrender.com` in your browser.

---

### Railway

1. Install the Railway CLI: `npm install -g @railway/cli`
2. Login: `railway login`
3. Create a project: `railway new`
4. Set environment variables:
   ```bash
   railway variables set GEMINI_API_KEY=your_key_here
   railway variables set SECRET_KEY=your_secret_here
   railway variables set FLASK_ENV=production
   ```
5. Deploy: `railway up`
6. Get your URL: `railway open`

---

### Google Cloud Run

```bash
# Install and configure gcloud CLI first
# https://cloud.google.com/sdk/docs/install

# Build and push Docker image
gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/weatherwise

# Deploy to Cloud Run
gcloud run deploy weatherwise \
  --image gcr.io/YOUR_PROJECT_ID/weatherwise \
  --platform managed \
  --region asia-south1 \
  --allow-unauthenticated \
  --set-env-vars GEMINI_API_KEY=your_key,SECRET_KEY=your_secret,FLASK_ENV=production
```

> **Note:** A `Dockerfile` will be needed for Cloud Run. See the Dockerfile below.

<details>
<summary>📄 Dockerfile for Cloud Run</summary>

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV FLASK_ENV=production
EXPOSE 8080

CMD ["gunicorn", "wsgi:app", "--workers", "2", "--bind", "0.0.0.0:8080", "--timeout", "120"]
```

</details>

---

## 📡 API Reference

All API endpoints accept/return JSON. Rate limit: **10 requests/minute per IP** for AI endpoints.

### `GET /api/weather?city={city_name}`

Fetch current weather for a city.

**Response:**
```json
{
  "city": "Mumbai",
  "current": {
    "temperature": 28.5,
    "windspeed": 22.0,
    "description": "Heavy rain",
    "precipitation": 5.2,
    "humidity": 87
  },
  "forecast_summary": {
    "total_precipitation_24h": 72.0,
    "max_rain_probability": 95,
    "monsoon_alert_level": "orange"
  }
}
```

---

### `POST /api/chat`

Conversational AI assistant.

**Request:**
```json
{
  "message": "What should I do if my basement floods?",
  "language": "Hindi",
  "city": "Mumbai"
}
```

**Response:**
```json
{ "reply": "AI response in Hindi..." }
```

---

### `POST /api/preparedness-plan`

Generate a personalised preparedness plan.

**Request:**
```json
{
  "location": "Pune",
  "family_size": 4,
  "vulnerabilities": ["elderly", "infant"],
  "phase": "active-monsoon",
  "language": "English"
}
```

**Response:**
```json
{ "plan": "## Your Personalised Plan\n..." }
```

---

### `POST /api/checklist`

Generate an emergency checklist.

**Request:**
```json
{
  "location": "Chennai",
  "housing_type": "apartment",
  "family_size": 3,
  "language": "Tamil"
}
```

---

### `POST /api/travel-advisory`

Get a travel safety advisory.

**Request:**
```json
{
  "origin": "Bangalore",
  "destination": "Coorg",
  "travel_date": "2025-08-15",
  "transport_mode": "car",
  "language": "English"
}
```

---

### `POST /api/alerts`

Generate colour-coded safety alerts.

**Request:**
```json
{
  "location": "Kolkata",
  "phase": "during",
  "language": "Bengali"
}
```

---

## 🔒 Security

| Measure | Implementation |
|---------|---------------|
| **API Key** | Stored in `.env`, never in code or version control |
| **Rate Limiting** | Flask-Limiter: 10/min for AI, 30/min for weather, 200/day global |
| **Input Sanitisation** | All user inputs HTML-escaped and length-validated |
| **XSS Prevention** | CSP headers + Jinja2 auto-escaping + JS `escapeHtml()` |
| **Clickjacking** | `X-Frame-Options: DENY` |
| **MIME Sniffing** | `X-Content-Type-Options: nosniff` |
| **Session Security** | `HttpOnly`, `SameSite=Lax`, `Secure` (in production) |
| **Prompt Injection** | User input sanitised before being included in AI prompts |
| **Gemini Safety** | `BLOCK_MEDIUM_AND_ABOVE` safety thresholds enabled |

---

## 📁 Project Structure

```
PromptWars-WeatherWise/
├── app/
│   ├── __init__.py          # Application factory
│   ├── config.py            # Dev/Prod/Test config
│   ├── routes/
│   │   ├── main.py          # Page routes (/, /dashboard, /health)
│   │   └── api.py           # AI API endpoints
│   ├── services/
│   │   ├── gemini_service.py # Google Gemini AI wrapper
│   │   └── weather_service.py# Open-Meteo weather data
│   ├── utils/
│   │   └── validators.py    # Input validation & sanitisation
│   ├── static/
│   │   ├── css/style.css    # Glassmorphism dark theme
│   │   └── js/app.js        # Frontend logic
│   └── templates/
│       ├── base.html        # Base layout
│       ├── index.html       # Landing page
│       └── dashboard.html   # Main app
├── tests/
│   ├── test_routes.py       # Route integration tests
│   ├── test_services.py     # Service unit tests
│   └── test_validators.py   # Validator unit tests
├── .env.example             # Environment variable template
├── .gitignore
├── requirements.txt
├── run.py                   # Dev entry point
├── wsgi.py                  # Production WSGI entry
├── Procfile                 # For Render/Heroku
└── README.md
```

---

## 🌍 Supported Languages

English · हिंदी (Hindi) · বাংলা (Bengali) · தமிழ் (Tamil) · తెలుగు (Telugu) · मराठी (Marathi) · ગુજરાતી (Gujarati) · ಕನ್ನಡ (Kannada) · മലയാളം (Malayalam) · ਪੰਜਾਬੀ (Punjabi) · ଓଡ଼ିଆ (Odia) · اردو (Urdu)

---

## 🆘 Emergency Contacts (India)

| Service | Number |
|---------|--------|
| NDRF (National Disaster Response Force) | 011-24363260 |
| Police | 100 |
| Ambulance | 108 |
| Fire Brigade | 101 |
| Disaster Management Helpline | 1078 |

---

## ⚠️ Disclaimer

WeatherWise AI responses are for **guidance only**. Always follow official advisories from the India Meteorological Department (IMD), National Disaster Management Authority (NDMA), and local emergency services during actual weather events.

---

*Built for India's monsoon season · Powered by Google Gemini AI*
