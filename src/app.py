import os
import io
import uvicorn
import pandas as pd
from typing import Optional
from fastapi import FastAPI, UploadFile, File, Header, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from analyzer import PortfolioAnalyzer
from integrations.kite import KiteIntegration
from integrations.upstox import UpstoxIntegration

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

@app.post("/api/analyze")
async def analyze(
    file: UploadFile = File(...),
    x_model: Optional[str] = Header("gpt-4o-mini"),
    x_api_key: Optional[str] = Header(None),
    x_base_url: Optional[str] = Header(None)
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
async def upstox_login():
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
    x_base_url: Optional[str] = Header(None)
):
    try:
        data = await request.json()
        holdings = data.get("holdings", [])
        
        import pandas as pd
        portfolio_df = pd.DataFrame(holdings)
        
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
    x_base_url: Optional[str] = Header(None)
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

# Mount static files directory
static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
os.makedirs(static_dir, exist_ok=True)
app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")

if __name__ == "__main__":
    # Start the server locally
    port = int(os.getenv("PORT", 8000))
    print(f"🚀 Starting Portfolio Diversification Analyzer server at http://localhost:{port}")
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=True)
