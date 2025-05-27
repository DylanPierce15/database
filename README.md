# 📚 Library Logger App

A web-based system for logging and monitoring student check-ins and check-outs at the library.

## 🚀 Features

- Student sign-in/sign-out with timestamps
- Admin view of all logs
- Real-time updates using WebSockets (Socket.IO)
- Tracks who is currently signed in
- Timezone formatting for EST

## 🛠️ Tech Stack

- Python + Flask
- Flask-SocketIO
- Jinja2 templating
- HTML/CSS/JS
- SQLite (or PostgreSQL/MySQL)
- Optional: Flask-Migrate for DB migrations

## 📦 Installation

```bash
git clone https://github.com/your-username/library-logger.git
cd library-logger
python -m venv venv
source venv/bin/activate   # or venv\Scripts\activate on Windows
pip install -r requirements.txt

