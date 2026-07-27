# 🎯 Price Sniper

A premium, modern e-commerce price monitor and tracking system built with **Django**, **Celery**, and **Redis**. It tracks products from **Flipkart** and **Amazon**, records historical values, and sends automated email alerts the second a product hits a user's target price.

---

## ✨ Features

- **Guest Landing Page**: A modern glassmorphic landing page with details, call-to-actions, and live preview counters.
- **Dynamic Dashboard**: Responsive dark-theme dashboard with options to add product URLs, delete trackers, and edit target prices inline.
- **Smart Scraper**: Scrapes page titles and current prices dynamically. Re-adding the same URL updates target prices rather than duplicating trackers.
- **Email Verification**: Sends secure tokens to activate newly registered accounts.
- **Intelligent Alerts**: Compares prices and alerts users instantly. Includes duplicate spam protection via notified pricing check.
- **Admin Analytics Dashboard**: Custom Django Admin themed with `django-jazzmin` containing:
  - Real-time counters (Shoppers, monitored items, active trackers, met alerts).
  - Built-in Chart.js doughnut and bar graphs tracking alert statuses and top popular products.
  - Custom column list displays with live-link anchors and toggle checkmarks.

---

## 🚀 Setup & Installation

### 1. Clone & Set Up Environment
```bash
# Set up Python virtual environment
python -m venv venv
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment Variables
Create a `.env` file in the root directory:
```env
EMAIL_USER=your_email@gmail.com
EMAIL_PASS=your_email_app_password
```

### 3. Database & Migrations
```bash
python manage.py migrate
python manage.py createsuperuser
```

---

## 🏃 Running the Application

To run the application locally, you need three processes running concurrently:

### 1. Redis Server
Ensure your local Redis server is running (e.g. via Docker or WSL):
```bash
redis-server
```

### 2. Django Server
```bash
python manage.py runserver
```
Visit http://127.0.0.1:8000/ to access the application.

### 3. Celery Worker (Windows Solo Pool)
```bash
celery -A config worker --loglevel=info -P solo
```

### 4. Celery Beat Scheduler
```bash
celery -A config beat --loglevel=info
```
