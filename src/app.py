import os
import io
import uvicorn
import pandas as pd
from typing import Optional
from fastapi import FastAPI, UploadFile, File, Header, HTTPException, Request, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from analyzer import PortfolioAnalyzer
from integrations.kite import KiteIntegration
from integrations.upstox import UpstoxIntegration
from services.cas_parser import parse_cdsl_cas

# Database & Scheduler Integrations
from db import init_db, get_db, UserSubscription, UserPortfolio, User
from scheduler import start_scheduler, stop_scheduler, run_daily_monitoring_job
from sqlalchemy.orm import Session
from fastapi import Depends

# Authentication Utilities
from auth_utils import (
    generate_salt,
    hash_password,
    verify_password,
    create_session,
    get_user_id_by_session,
    destroy_session
)

# Load environment variables
load_dotenv()

app = FastAPI(
    title="Portfolio Diversification Analyzer API",
    description="Backend API for GenAI-powered portfolio diversification insights.",
    version="1.0.0"
)

# Enable CORS for development flexibility
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Startup / Shutdown Hooks to initialize DB and run daily scheduler
@app.on_event("startup")
def on_startup():
    print("🚀 Initializing PostgreSQL Database...")
    try:
        init_db()
        print("✅ PostgreSQL Database Initialized Successfully.")
    except Exception as e:
        print(f"❌ Failed to initialize database: {e}")
    print("⏰ Starting background daily news agent...")
    start_scheduler()

@app.on_event("shutdown")
def on_shutdown():
    print("🛑 Shutting down background daily scheduler...")
    stop_scheduler()

# --- AUTHENTICATION DEPENDENCY & ENDPOINTS ---

def get_current_user_id(request: Request) -> int:
    token = request.cookies.get("session_token")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated. Please log in.")
    user_id = get_user_id_by_session(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Session expired. Please log in again.")
    return user_id

@app.post("/api/auth/signup")
async def signup(request: Request, db: Session = Depends(get_db)):
    try:
        data = await request.json()
        email = data.get("email", "").strip().lower()
        password = data.get("password", "")

        if not email or "@" not in email:
            raise HTTPException(status_code=400, detail="A valid email address is required.")
        if len(password) < 6:
            raise HTTPException(status_code=400, detail="Password must be at least 6 characters.")

        existing = db.query(User).filter(User.email == email).first()
        if existing:
            raise HTTPException(status_code=400, detail="An account with this email already exists.")

        salt = generate_salt()
        pwd_hash = hash_password(password, salt)

        user = User(email=email, salt=salt, password_hash=pwd_hash)
        db.add(user)
        db.commit()

        return JSONResponse(content={"success": True, "message": "Account created successfully. You can now log in!"})
    except HTTPException as he:
        raise he
    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})

@app.post("/api/auth/login")
async def login(request: Request, db: Session = Depends(get_db)):
    try:
        data = await request.json()
        email = data.get("email", "").strip().lower()
        password = data.get("password", "")

        user = db.query(User).filter(User.email == email).first()
        if not user or not verify_password(password, user.salt, user.password_hash):
            raise HTTPException(status_code=401, detail="Invalid email or password.")

        token = create_session(user.id)

        response = JSONResponse(content={"success": True, "message": "Logged in successfully!"})
        response.set_cookie(
            key="session_token",
            value=token,
            httponly=True,
            max_age=14 * 24 * 3600, # 14 days
            samesite="lax",
            secure=False # Set to True in production over HTTPS
        )
        return response
    except HTTPException as he:
        raise he
    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})

@app.post("/api/auth/logout")
async def logout(request: Request):
    token = request.cookies.get("session_token")
    if token:
        destroy_session(token)
    response = JSONResponse(content={"success": True, "message": "Logged out successfully."})
    response.delete_cookie("session_token")
    return response

@app.get("/api/auth/me")
async def get_me(user_id: int = Depends(get_current_user_id), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    
    holdings = []
    sub_active = False
    if user.subscription:
        sub_active = user.subscription.is_active
        if user.subscription.portfolio:
            holdings = user.subscription.portfolio.holdings_json

    return JSONResponse(content={
        "success": True,
        "email": user.email,
        "is_subscribed": sub_active,
        "holdings": holdings
    })

@app.post("/api/analyze")
async def analyze(
    file: UploadFile = File(...),
    x_model: Optional[str] = Header("gpt-4o-mini"),
    x_api_key: Optional[str] = Header(None),
    x_base_url: Optional[str] = Header(None),
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """
    Parses the uploaded portfolio CSV, computes percentage allocations,
    and runs the OpenAI SDK against the chosen model/proxy 
    to assess portfolio diversification.
    """
    # Verify file extension
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are supported.")

    model_name = (x_model or "gpt-4o-mini").strip()

    try:
        # Read the uploaded file contents into memory
        contents = await file.read()
        csv_string = contents.decode("utf-8")
        csv_io = io.StringIO(csv_string)

        # Initialize the analyzer with selected model, key, and base URL
        analyzer = PortfolioAnalyzer(model=model_name, api_key=x_api_key, base_url=x_base_url)

        # Load and validate the portfolio
        portfolio_df = analyzer.load_portfolio(csv_io)
        
        # Calculate breakdowns
        allocations = analyzer.calculate_allocations(portfolio_df)

        # Get GenAI advice
        report = analyzer.generate_diversification_report(portfolio_df, allocations)

        # Clean NaN/Inf in DataFrames to ensure clean JSON serialization
        asset_type_df = allocations["asset_type_breakdown"].fillna("")
        sector_df = allocations["sector_breakdown"].fillna("")
        market_cap_df = allocations.get("market_cap_breakdown", pd.DataFrame()).fillna("")
        risk_df = allocations.get("risk_breakdown", pd.DataFrame()).fillna("")

        # Include percentages on raw assets list to render them in a beautiful table
        total_val = allocations["total_value"]
        assets_list = portfolio_df.copy()
        assets_list["Percentage"] = (assets_list["Current Value"] / total_val) * 100
        assets_list = assets_list.fillna("").to_dict(orient="records")

        # Automatically overwrite the portfolio holdings in the database
        sub = db.query(UserSubscription).filter(UserSubscription.user_id == user_id).first()
        if not sub:
            user = db.query(User).filter(User.id == user_id).first()
            sub = UserSubscription(
                user_id=user_id,
                email=user.email if user else "",
                is_active=False,
                model=model_name,
                api_key=x_api_key
            )
            db.add(sub)
            db.commit()
            db.refresh(sub)
            
        portfolio = db.query(UserPortfolio).filter(UserPortfolio.subscription_id == sub.id).first()
        if not portfolio:
            portfolio = UserPortfolio(subscription_id=sub.id, holdings_json=assets_list)
            db.add(portfolio)
        else:
            portfolio.holdings_json = assets_list
            
        db.commit()

        response_data = {
            "success": True,
            "total_value": float(total_val),
            "asset_type_breakdown": asset_type_df.to_dict(orient="records"),
            "sector_breakdown": sector_df.to_dict(orient="records"),
            "market_cap_breakdown": market_cap_df.to_dict(orient="records") if not market_cap_df.empty else [],
            "risk_breakdown": risk_df.to_dict(orient="records") if not risk_df.empty else [],
            "benchmark": allocations.get("benchmark_comparison", {}),
            "assets": assets_list,
            "report": report,
            "model": model_name,
            "has_api_key": bool(analyzer.api_key)
        }

        return JSONResponse(content=response_data)

    except ValueError as e:
        # Handle format/parsing errors gracefully (400 Bad Request)
        return JSONResponse(
            status_code=400,
            content={"success": False, "error": f"CSV Format Error: {str(e)}"}
        )
    except Exception as e:
        # Handle other internal exceptions gracefully
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": f"An error occurred: {str(e)}"}
        )

@app.post("/api/analyze/cas")
async def analyze_cas(
    file: UploadFile = File(...),
    password: str = Form(""),
    x_model: Optional[str] = Header("gpt-4o-mini"),
    x_api_key: Optional[str] = Header(None),
    x_base_url: Optional[str] = Header(None),
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """
    Parses the uploaded Consolidated Account Statement (CAS) PDF, 
    decrypts it using the user-provided password, standardizes assets,
    computes allocations, and runs OpenAI SDK to assess diversification.
    """
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF statement files are supported.")

    model_name = (x_model or "gpt-4o-mini").strip()

    try:
        # Read the uploaded PDF file contents into memory
        contents = await file.read()
        pdf_io = io.BytesIO(contents)

        # Parse the CAS statement using pypdf parser
        parsed_df = parse_cdsl_cas(pdf_io, password.strip())

        # Initialize the analyzer with selected model, key, and base URL
        analyzer = PortfolioAnalyzer(model=model_name, api_key=x_api_key, base_url=x_base_url)

        # Enrich the parsed portfolio using existing analyzer logic
        portfolio_df = analyzer.enrich_portfolio(parsed_df)
        
        # Calculate breakdowns
        allocations = analyzer.calculate_allocations(portfolio_df)

        # Get GenAI advice
        report = analyzer.generate_diversification_report(portfolio_df, allocations)

        # Clean NaN/Inf in DataFrames to ensure clean JSON serialization
        asset_type_df = allocations["asset_type_breakdown"].fillna("")
        sector_df = allocations["sector_breakdown"].fillna("")
        market_cap_df = allocations.get("market_cap_breakdown", pd.DataFrame()).fillna("")
        risk_df = allocations.get("risk_breakdown", pd.DataFrame()).fillna("")

        # Include percentages on raw assets list to render them in a beautiful table
        total_val = allocations["total_value"]
        assets_list = portfolio_df.copy()
        assets_list["Percentage"] = (assets_list["Current Value"] / total_val) * 100
        assets_list = assets_list.fillna("").to_dict(orient="records")

        # Automatically overwrite the portfolio holdings in the database
        sub = db.query(UserSubscription).filter(UserSubscription.user_id == user_id).first()
        if not sub:
            user = db.query(User).filter(User.id == user_id).first()
            sub = UserSubscription(
                user_id=user_id,
                email=user.email if user else "",
                is_active=False,
                model=model_name,
                api_key=x_api_key
            )
            db.add(sub)
            db.commit()
            db.refresh(sub)
            
        portfolio = db.query(UserPortfolio).filter(UserPortfolio.subscription_id == sub.id).first()
        if not portfolio:
            portfolio = UserPortfolio(subscription_id=sub.id, holdings_json=assets_list)
            db.add(portfolio)
        else:
            portfolio.holdings_json = assets_list
            
        db.commit()

        response_data = {
            "success": True,
            "total_value": float(total_val),
            "asset_type_breakdown": asset_type_df.to_dict(orient="records"),
            "sector_breakdown": sector_df.to_dict(orient="records"),
            "market_cap_breakdown": market_cap_df.to_dict(orient="records") if not market_cap_df.empty else [],
            "risk_breakdown": risk_df.to_dict(orient="records") if not risk_df.empty else [],
            "benchmark": allocations.get("benchmark_comparison", {}),
            "assets": assets_list,
            "report": report,
            "model": model_name,
            "has_api_key": bool(analyzer.api_key)
        }

        return JSONResponse(content=response_data)

    except ValueError as e:
        return JSONResponse(
            status_code=400,
            content={"success": False, "error": f"CAS Parser Error: {str(e)}"}
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": f"An error occurred during CAS parsing: {str(e)}"}
        )

@app.get("/api/auth/kite/login")
async def kite_login():
    """Returns the login URL for Kite Connect."""
    try:
        kite = KiteIntegration()
        login_url = kite.get_login_url()
        return JSONResponse(content={"success": True, "login_url": login_url})
    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})

@app.get("/api/auth/kite/callback")
async def kite_callback(
    request_token: str, 
    action: Optional[str] = None, 
    status: Optional[str] = None
):
    """
    Handles the redirect from Kite Connect. 
    Exchanges the request_token for an access_token, fetches holdings,
    analyzes the portfolio, and returns an HTML page that posts the result
    back to the parent window.
    """
    if status != "success":
        error_html = "<html><body><script>window.opener.postMessage({success: false, error: 'Login failed or was cancelled.'}, '*'); window.close();</script></body></html>"
        return HTMLResponse(content=error_html)

    try:
        kite = KiteIntegration()
        kite.generate_session(request_token)
        holdings = kite.fetch_holdings()
        
        # Convert to Analyzer format
        portfolio_df = kite.to_analyzer_format(holdings)
        
        # We need a model and api_key to run the analyzer. We'll use defaults for now,
        # but the UI should ideally pass them via localStorage/cookies or we just skip the report if not available.
        # Let's run basic allocations without GenAI report, or try to run with default env keys.
        model_name = "gpt-4o-mini"
        analyzer = PortfolioAnalyzer(model=model_name)
        
        # Calculate breakdowns
        allocations = analyzer.calculate_allocations(portfolio_df)

        # Get GenAI advice
        report = analyzer.generate_diversification_report(portfolio_df, allocations)

        # Clean NaN/Inf in DataFrames to ensure clean JSON serialization
        asset_type_df = allocations["asset_type_breakdown"].fillna("")
        sector_df = allocations["sector_breakdown"].fillna("")
        market_cap_df = allocations.get("market_cap_breakdown", pd.DataFrame()).fillna("")
        risk_df = allocations.get("risk_breakdown", pd.DataFrame()).fillna("")

        # Include percentages on raw assets list to render them in a beautiful table
        total_val = allocations["total_value"]
        assets_list = portfolio_df.copy()
        assets_list["Percentage"] = (assets_list["Current Value"] / total_val) * 100
        assets_list = assets_list.fillna("").to_dict(orient="records")

        import json
        response_data = {
            "success": True,
            "total_value": float(total_val),
            "asset_type_breakdown": asset_type_df.to_dict(orient="records"),
            "sector_breakdown": sector_df.to_dict(orient="records"),
            "market_cap_breakdown": market_cap_df.to_dict(orient="records") if not market_cap_df.empty else [],
            "risk_breakdown": risk_df.to_dict(orient="records") if not risk_df.empty else [],
            "benchmark": allocations.get("benchmark_comparison", {}),
            "assets": assets_list,
            "report": report,
            "model": model_name,
            "has_api_key": bool(analyzer.api_key)
        }
        
        # Escape the JSON for safe injection into the script block
        safe_json = json.dumps(response_data).replace("</script>", "<\\/script>")
        
        success_html = f"""
        <html>
            <head><title>Kite Connected</title></head>
            <body>
                <h2 style="font-family: sans-serif; text-align: center; margin-top: 50px;">Analysis Complete! You can close this window.</h2>
                <script>
                    window.opener.postMessage({safe_json}, '*');
                    setTimeout(() => window.close(), 2000);
                </script>
            </body>
        </html>
        """
        return HTMLResponse(content=success_html)

    except Exception as e:
        import json
        error_msg = str(e)
        print(f"❌ Kite Connect Callback Error: {error_msg}")
        error_data = json.dumps({"success": False, "error": error_msg})
        error_html = f"<html><body><script>window.opener.postMessage({error_data}, '*'); window.close();</script></body></html>"
        return HTMLResponse(content=error_html)
@app.get("/api/auth/upstox/login")
async def upstox_login(user_id: int = Depends(get_current_user_id)):
    """Returns the login URL for Upstox."""
    try:
        upstox = UpstoxIntegration()
        login_url = upstox.get_login_url()
        return JSONResponse(content={"success": True, "login_url": login_url})
    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})

@app.get("/api/auth/upstox/callback")
async def upstox_callback(code: Optional[str] = None):
    """
    Handles the redirect from Upstox. 
    """
    if not code:
        error_html = "<html><body><script>window.opener.postMessage({success: false, error: 'Login failed or was cancelled.'}, '*'); window.close();</script></body></html>"
        return HTMLResponse(content=error_html)

    try:
        upstox = UpstoxIntegration()
        upstox.generate_session(code)
        holdings = upstox.fetch_holdings()
        
        portfolio_df = upstox.to_analyzer_format(holdings)
        
        import json
        response_data = {
            "success": True,
            "is_raw_holdings": True,
            "holdings": portfolio_df.to_dict(orient="records")
        }
        
        safe_json = json.dumps(response_data).replace("</script>", "<\\/script>")
        
        success_html = f"""
        <html>
            <head><title>Upstox Connected</title></head>
            <body>
                <h2 style="font-family: sans-serif; text-align: center; margin-top: 50px;">Fetching Portfolio...</h2>
                <script>
                    window.opener.postMessage({safe_json}, '*');
                    setTimeout(() => window.close(), 100);
                </script>
            </body>
        </html>
        """
        return HTMLResponse(content=success_html)

    except Exception as e:
        import json
        error_msg = str(e)
        print(f"❌ Upstox Callback Error: {error_msg}")
        error_data = json.dumps({"success": False, "error": error_msg})
        error_html = f"<html><body><script>window.opener.postMessage({error_data}, '*'); window.close();</script></body></html>"
        return HTMLResponse(content=error_html)

@app.post("/api/analyze_holdings")
async def analyze_holdings(
    request: Request,
    x_model: Optional[str] = Header("gpt-4o-mini"),
    x_api_key: Optional[str] = Header(None),
    x_base_url: Optional[str] = Header(None),
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    try:
        data = await request.json()
        holdings = data.get("holdings", [])
        
        # Standardize known column aliases for JSON holdings
        alias_mapping = {
            "buy_price": "Buy Price",
            "avg_price": "Buy Price",
            "average_price": "Buy Price",
            "quantity": "Quantity",
            "qty": "Quantity",
            "shares": "Quantity",
            "averageBuyPrice": "Buy Price",
            "averagePrice": "Buy Price"
        }
        for h in holdings:
            for k in list(h.keys()):
                if k in alias_mapping:
                    h[alias_mapping[k]] = h[k]
        
        import pandas as pd
        portfolio_df = pd.DataFrame(holdings)
        
        # Handle optional columns safely
        if "Buy Price" in portfolio_df.columns:
            portfolio_df["Buy Price"] = pd.to_numeric(portfolio_df["Buy Price"], errors="coerce").fillna(0.0)
        if "Quantity" in portfolio_df.columns:
            portfolio_df["Quantity"] = pd.to_numeric(portfolio_df["Quantity"], errors="coerce").fillna(0.0)
        
        model_name = (x_model or "gpt-4o-mini").strip()
        analyzer = PortfolioAnalyzer(model=model_name, api_key=x_api_key, base_url=x_base_url)
        
        allocations = analyzer.calculate_allocations(portfolio_df)
        report = analyzer.generate_diversification_report(portfolio_df, allocations)

        asset_type_df = allocations["asset_type_breakdown"].fillna("")
        sector_df = allocations["sector_breakdown"].fillna("")
        market_cap_df = allocations.get("market_cap_breakdown", pd.DataFrame()).fillna("")
        risk_df = allocations.get("risk_breakdown", pd.DataFrame()).fillna("")

        total_val = allocations["total_value"]
        assets_list = portfolio_df.copy()
        assets_list["Percentage"] = (assets_list["Current Value"] / total_val) * 100
        assets_list = assets_list.fillna("").to_dict(orient="records")

        # Automatically overwrite the portfolio holdings in the database
        sub = db.query(UserSubscription).filter(UserSubscription.user_id == user_id).first()
        if not sub:
            user = db.query(User).filter(User.id == user_id).first()
            sub = UserSubscription(
                user_id=user_id,
                email=user.email if user else "",
                is_active=False,
                model=model_name,
                api_key=x_api_key
            )
            db.add(sub)
            db.commit()
            db.refresh(sub)
            
        portfolio = db.query(UserPortfolio).filter(UserPortfolio.subscription_id == sub.id).first()
        if not portfolio:
            portfolio = UserPortfolio(subscription_id=sub.id, holdings_json=assets_list)
            db.add(portfolio)
        else:
            portfolio.holdings_json = assets_list
            
        db.commit()

        response_data = {
            "success": True,
            "total_value": float(total_val),
            "asset_type_breakdown": asset_type_df.to_dict(orient="records"),
            "sector_breakdown": sector_df.to_dict(orient="records"),
            "market_cap_breakdown": market_cap_df.to_dict(orient="records") if not market_cap_df.empty else [],
            "risk_breakdown": risk_df.to_dict(orient="records") if not risk_df.empty else [],
            "benchmark": allocations.get("benchmark_comparison", {}),
            "assets": assets_list,
            "report": report,
            "model": model_name,
            "has_api_key": bool(analyzer.api_key)
        }
        
        return JSONResponse(content=response_data)
        
    except Exception as e:
        import json
        error_msg = str(e)
        print(f"❌ Analyze Holdings Error: {error_msg}")
        return JSONResponse(status_code=500, content={"success": False, "error": error_msg})

@app.post("/api/chat")
async def chat_endpoint(
    request: Request,
    x_model: Optional[str] = Header("gpt-4o-mini"),
    x_api_key: Optional[str] = Header(None),
    x_base_url: Optional[str] = Header(None),
    user_id: int = Depends(get_current_user_id)
):
    try:
        data = await request.json()
        message = data.get("message", "")
        holdings = data.get("holdings", [])
        history = data.get("history", [])
        
        import pandas as pd
        portfolio_df = pd.DataFrame(holdings)
        
        model_name = (x_model or "gpt-4o-mini").strip()
        analyzer = PortfolioAnalyzer(model=model_name, api_key=x_api_key, base_url=x_base_url)
        
        reply = analyzer.chat(portfolio_df, message, history)
        return JSONResponse(content={"success": True, "reply": reply})
        
    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})

@app.get("/kaithhealthcheck")
@app.get("/kaithheathcheck")
async def healthcheck():
    """Health check endpoint for Leapcell."""
    return JSONResponse(content={"status": "ok"})

# --- AGENTIC DAILY MONITORING SUBSCRIPTION API ENDPOINTS ---

@app.post("/api/subscriptions/subscribe")
async def subscribe_daily(request: Request, user_id: int = Depends(get_current_user_id), db: Session = Depends(get_db)):
    """
    Subscribes a user to daily portfolio news impact reports and stores 
    their holdings for offline agent monitoring.
    """
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found.")

        data = await request.json()
        holdings = data.get("holdings", [])

        if not holdings:
            raise HTTPException(status_code=400, detail="Cannot subscribe an empty portfolio.")

        # Check or create subscription
        sub = db.query(UserSubscription).filter(UserSubscription.user_id == user.id).first()
        if not sub:
            sub = UserSubscription(
                user_id=user.id, 
                email=user.email, 
                is_active=True,
                model=data.get("model"),
                api_key=data.get("api_key")
            )
            db.add(sub)
            db.commit()
            db.refresh(sub)
        else:
            sub.is_active = True
            sub.model = data.get("model")
            sub.api_key = data.get("api_key")
            db.commit()

        # Check or create portfolio record
        portfolio = db.query(UserPortfolio).filter(UserPortfolio.subscription_id == sub.id).first()
        if not portfolio:
            portfolio = UserPortfolio(subscription_id=sub.id, holdings_json=holdings)
            db.add(portfolio)
        else:
            portfolio.holdings_json = holdings
            
        db.commit()
        
        return JSONResponse(content={
            "success": True, 
            "message": f"Successfully activated daily advisor email updates for {user.email}!"
        })
    except HTTPException as he:
        raise he
    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})

@app.post("/api/subscriptions/unsubscribe")
async def unsubscribe_daily(request: Request, user_id: int = Depends(get_current_user_id), db: Session = Depends(get_db)):
    """
    API endpoint to unsubscribe from email updates.
    """
    try:
        sub = db.query(UserSubscription).filter(UserSubscription.user_id == user_id).first()
        if not sub:
            return JSONResponse(status_code=404, content={"success": False, "error": "Subscription not found."})

        sub.is_active = False
        db.commit()

        return JSONResponse(content={
            "success": True, 
            "message": f"Successfully disabled daily monitoring updates."
        })
    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})

@app.get("/api/subscriptions/unsubscribe-direct")
async def unsubscribe_direct(email: str, db: Session = Depends(get_db)):
    """
    HTML direct one-click unsubscribe endpoint linked inside sent emails.
    """
    try:
        email = email.strip().lower()
        sub = db.query(UserSubscription).filter(UserSubscription.email == email).first()
        if sub:
            sub.is_active = False
            db.commit()

        unsubscribe_html = f"""
        <html>
            <head>
                <title>Unsubscribed — DiversifyAI</title>
                <style>
                    body {{
                        background-color: #0f172a;
                        color: #f1f5f9;
                        font-family: sans-serif;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        height: 100vh;
                        margin: 0;
                    }}
                    .card {{
                        background: #1e293b;
                        padding: 40px;
                        border-radius: 12px;
                        text-align: center;
                        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.3);
                        max-width: 400px;
                        border: 1px solid rgba(255, 255, 255, 0.05);
                    }}
                    h1 {{ color: #ef4444; margin-bottom: 10px; font-size: 24px; }}
                    p {{ color: #94a3b8; font-size: 14px; line-height: 1.5; }}
                    .btn {{
                        background: #4f46e5;
                        color: white;
                        text-decoration: none;
                        padding: 10px 20px;
                        border-radius: 6px;
                        display: inline-block;
                        margin-top: 20px;
                        font-size: 14px;
                    }}
                </style>
            </head>
            <body>
                <div class="card">
                    <h1>Alerts Disabled</h1>
                    <p>You have been successfully unsubscribed from daily reports.</p>
                    <a class="btn" href="/">Return to Dashboard</a>
                </div>
            </body>
        </html>
        """
        return HTMLResponse(content=unsubscribe_html)
    except Exception as e:
        return HTMLResponse(content=f"<h3>Error unsubscribing: {str(e)}</h3>", status_code=500)

@app.post("/api/subscriptions/trigger_test")
async def trigger_test_report(request: Request, user_id: int = Depends(get_current_user_id), db: Session = Depends(get_db)):
    """
    Manually triggers an instant news aggregated AI analysis and emails it 
    immediately to verify SMTP and agent operation.
    """
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found.")

        data = await request.json()
        holdings = data.get("holdings", [])

        if not holdings:
            raise HTTPException(status_code=400, detail="No portfolio loaded to analyze.")

        # Create or update subscription so we have valid keys in DB
        sub = db.query(UserSubscription).filter(UserSubscription.user_id == user.id).first()
        if not sub:
            sub = UserSubscription(
                user_id=user.id, 
                email=user.email, 
                is_active=True,
                model=data.get("model"),
                api_key=data.get("api_key")
            )
            db.add(sub)
            db.commit()
            db.refresh(sub)
        else:
            sub.is_active = True
            sub.model = data.get("model")
            sub.api_key = data.get("api_key")
            db.commit()

        # Create or update portfolio holdings
        portfolio = db.query(UserPortfolio).filter(UserPortfolio.subscription_id == sub.id).first()
        if not portfolio:
            portfolio = UserPortfolio(subscription_id=sub.id, holdings_json=holdings)
            db.add(portfolio)
        else:
            portfolio.holdings_json = holdings
            
        db.commit()

        # Force run daily worker job synchronously for this email
        job_result = await run_daily_monitoring_job(subscription_id=sub.id)
        
        if not job_result.get("success", False):
            raise Exception(job_result.get("error", "Failed to run advisor job"))

        processed_entry = job_result["processed"][0]
        email_sent = processed_entry.get("email_sent", False)
        
        message = f"Instant news advisory generated! "
        if email_sent:
            message += f"An intelligence report has been dispatched to {user.email}."
        else:
            message += f"Report calculated, but failed to deliver. Ensure SMTP credentials are set in .env."

        return JSONResponse(content={
            "success": True, 
            "message": message,
            "report": processed_entry.get("report", {})
        })
    except Exception as e:
        print(f"❌ Test Trigger Error: {e}")
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})


# Mount static files directory
static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
os.makedirs(static_dir, exist_ok=True)
app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")

if __name__ == "__main__":
    # Start the server locally
    port = int(os.getenv("PORT", 8000))
    print(f"🚀 Starting Portfolio Diversification Analyzer server at http://localhost:{port}")
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=True)
