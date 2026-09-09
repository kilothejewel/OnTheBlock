# OnTheBlock

**OnTheBlock** is a dual-platform solution (Web Application + Chrome Extension) designed to help users discover trendy places and create budget-based itineraries. Whether you're planning a night out or a weekend trip, OnTheBlock curates the hottest spots for you.

## 🚀 Vision

- **Discover**: Find trendy places using real-time data.
- **Plan**: Generate itineraries based on your budget and preferences.
- **Save**: Keep track of your favorite "Hotspots" and access them anywhere.
- **Go**: Seamless transition from browsing on the web to on-the-go access via mobile (coming soon).

## 🏗️ Architecture & Tech Stack

The project allows for code sharing and a unified backend API.

### **Core Stack**
- **Web App**: [Vite](https://vitejs.dev/) + React - the main platform UI (`web/`).
- **Backend/API**: [FastAPI](https://fastapi.tiangolo.com/) + [SQLAlchemy](https://www.sqlalchemy.org/) (`app/`).
- **Database**: PostgreSQL, accessed directly via SQLAlchemy / psycopg2 (SQLite is
  supported for local dev and tests via `OTB_DATABASE_URL`).
- **Auth**: Custom email/username + password authentication. Passwords are hashed
  with bcrypt (passlib) and sessions use signed JWT bearer tokens (python-jose).
- **Rate limiting**: slowapi, with stricter per-route limits on the OpenAI /
  Google Places-backed endpoints.
- **Styling**: Vanilla CSS for a custom, premium feel.

### **Data Source**
- **Google Places API**: For retrieving up-to-date information on places, ratings, and trends.

### **Structure**
```text
OnTheBlock/
├── app/              # FastAPI backend
│   ├── core/         # config, database, security (JWT), rate limiting
│   ├── models/       # SQLAlchemy models
│   ├── routers/      # auth, hotspots, itineraries
│   └── services/     # Google Places + OpenAI itinerary generation
├── tests/            # pytest suite (in-memory SQLite, mocked externals)
├── web/              # Vite + React web app
└── README.md
```

## 📱 Mobile Strategy (Future)
The architecture is designed "API-First". The FastAPI backend is the central brain. Future mobile apps (React Native) will consume the same API endpoints used by the web app, ensuring data consistency and centralized logic.

## 🛠️ Getting Started

### Prerequisites
- Python 3.11+
- Node.js (v18+) and npm
- PostgreSQL (or use SQLite locally via `OTB_DATABASE_URL`)

### Setup
1. **Clone the repository**:
   ```bash
   git clone https://github.com/your-username/OnTheBlock.git
   cd OnTheBlock
   ```

2. **Backend (FastAPI)**:
   ```bash
   python -m venv .venv && source .venv/Scripts/activate  # or .venv/bin/activate
   pip install -r requirements.txt
   cp .env.template .env    # then fill in OTB_SECRET_KEY, OTB_OPENAI_API_KEY, etc.
   uvicorn app.main:app --reload
   ```

3. **Web App**:
   ```bash
   cd web
   npm install
   cp .env.example .env     # adjust VITE_API_BASE if the API is not on :8000
   npm run dev
   ```

4. **Tests**:
   ```bash
   pytest
   ```
