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
- **Web App**: [Next.js](https://nextjs.org/) (React) - The main platform and API backend.
- **Chrome Extension**: [Vite](https://vitejs.dev/) + React - A lightweight companion for browsing context.
- **Backend/API**: Next.js API Routes (Serverless).
- **Database Description**: [Supabase](https://supabase.com/) (PostgreSQL) for Auth, User Data, and "Hotspots".
- **Styling**: Vanilla CSS / CSS Modules for a custom, premium feel.

### **Data Source**
- **Google Places API**: For retrieving up-to-date information on places, ratings, and trends.

### **Structure**
```text
OnTheBlock/
├── web/              # Main Web App + API Backend (Next.js)
│   └── src/app/api/  # Centralized API endpoints for Web & Apps
├── extension/        # Chrome Extension (Vite + React)
└── README.md
```

## 📱 Mobile Strategy (Future)
The architecture is designed "API-First". The Next.js backend will serve as the central brain. Future mobile apps (React Native) will consume the same API endpoints used by the Web App and Chrome Extension, ensuring data consistency and centralized logic.

## 🛠️ Getting Started

### Prerequisites
- Node.js (v18+)
- npm / yarn / pnpm

### Setup
1. **Clone the repository**:
   ```bash
   git clone https://github.com/your-username/OnTheBlock.git
   cd OnTheBlock
   ```

2. **Web App**:
   ```bash
   cd web
   npm install
   npm run dev
   ```

3. **Chrome Extension**:
   ```bash
   cd extension
   npm install
   npm run build
   # Load the 'dist' folder as an unpacked extension in Chrome
   ```
