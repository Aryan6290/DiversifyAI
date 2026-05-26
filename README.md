# DiversifyAI — GenAI Portfolio Diversification Analyzer

DiversifyAI is a production-ready, high-fidelity Web Application and API that analyzes your stock and mutual fund investments using Google's Gemini generative AI models. The system features a responsive, beautifully styled dark glassmorphic dashboard complete with drag-and-drop file upload, interactive animated charts, database-backed persistent authentication, Consolidated Account Statement (CAS) PDF parsing, and real-time strategic GenAI advisory.

---

## 🌟 Premium Features 

- **📊 High-Fidelity Tabular UI**: A completely custom holdings grid displaying **Invested Value**, **Current Value**, **Total Profit/Loss** (with custom cross-platform SVG indicators), and **Percent Allocation** with unit averages/NAVs clearly shown.
- **📂 CDSL CAS PDF Parsing**: Fully integrated consolidated account statement parser supporting password-encrypted PDFs to automatically extract mutual funds and demat equity holdings.
- **🔒 Persistent Database Sessions**: Durable session state managed via SQLite/PostgreSQL, ensuring user logins remain completely persistent across server restarts and auto-reloads.
- **🤖 GenAI Strategic Advisor**: Leverages Gemini (`gemini-2.5-flash` or custom models) to analyze asset correlations, detect sector concentration, compute volatility indicators, and deliver tailored strategies.
- **📈 Interactive Breakdown Visualizations**: Beautiful, animated doughnut charts powered by `Chart.js` reflecting your real-time allocations by Asset Type, Sector, Market Capitalization, and Risk/Volatility.
- **⚡ Proactive Daily Alerts**: Background scheduler executing every morning at 8:00 AM to monitor market news impact vectors on your holdings and deliver actionable intelligence to your inbox.
- **💬 Conversational AI Chat Widget**: Integrated interactive chatbot allowing you to query your portfolio dynamically (e.g., *"Which stock is my highest risk?"*, *"Suggest ways to reduce volatility"*).

---

## 📁 Directory Structure

```
Sample/
├── .env.template             # Template environment variables (GEMINI_API_KEY)
├── requirements.txt          # Python packages (fastapi, pandas, pypdf, SQLAlchemy, etc.)
├── README.md                 # Product guide and instructions
├── data/
│   └── sample_portfolio.csv  # Example CSV portfolio
└── src/
    ├── __init__.py
    ├── app.py                # Primary FastAPI web server & routes
    ├── analyzer.py           # Core portfolio analytics & GenAI reporting
    ├── db.py                 # Database models (Users, Portfolios, UserSession, Subscriptions)
    ├── auth_utils.py         # Persistent session utility functions
    ├── scheduler.py          # Background daily monitoring engine
    ├── services/
    │   ├── cas_parser.py     # Consolidated Account Statement (CAS) PDF parser
    │   ├── metadata_service.py # Real-time stock metadata classifier & yfinance interface
    │   └── email_service.py  # GenAI automated daily email reporter
    └── static/               # Premium glassmorphic frontend
        ├── index.html        # Glassmorphic layout structure
        ├── styles.css        # Dashboard styling system & CSS Grid responsive locks
        └── app.js            # Interactive app logic & Chart.js orchestration
```

---

## 🚀 Setup & Installation

### 1. Clone & Initialize Environment
Ensure you have Python 3.9+ installed, then set up the virtual environment:
```bash
# Navigate to the project root
cd "/Users/aryanbarnwal/Projects/GenAI Project/Sample"

# Create a virtual environment
python3 -m venv venv

# Activate the virtual environment
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment Variables
Copy `.env.template` to `.env`:
```bash
cp .env.template .env
```
Open `.env` and fill in your details:
```env
GEMINI_API_KEY=AIzaSy...
# Optional details for the email alert system:
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
```
*(If you do not have an API key, you can get one from [Google AI Studio](https://aistudio.google.com/) or enter a custom key directly in the web dashboard header during runtime.)*

---

## 💻 Running the Application

### Launch the Web Server
With your virtual environment active, run:
```bash
cd src
../venv/bin/python -m uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

Open **`http://localhost:8000`** in your browser!

### How to Analyze:
1. Register/Log in to your account.
2. Drag and drop either:
   - **A standard CSV file** (e.g. `data/sample_portfolio.csv`).
   - **Your password-encrypted CDSL CAS PDF** (provide the password in the decryption box).
3. Click **"Analyze Portfolio"** to generate real-time metrics, interactive allocations, and advisory reports.
4. Try out **What-If Simulations** or converse directly with the **GenAI Chatbot** at the bottom of the page!
