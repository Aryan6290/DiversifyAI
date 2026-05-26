import os
import json
import logging
import pandas as pd
from typing import Dict, Any, List
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy.orm import Session
from dotenv import load_dotenv

from db import SessionLocal, UserSubscription, UserPortfolio, DailyReport
from analyzer import PortfolioAnalyzer
from services.news_service import NewsService
from services.email_service import EmailService

load_dotenv()
logger = logging.getLogger("SchedulerService")

# Initialize background scheduler
scheduler = AsyncIOScheduler()

# Initialize core services
news_service = NewsService()
email_service = EmailService()

async def run_daily_monitoring_job(subscription_id: int = None, force_send_email: str = None) -> Dict[str, Any]:
    """
    Core monitoring task. Can run for all active subscribers (cron trigger)
    or for a single user (forced manually via the dashboard test trigger).
    """
    logger.info("Starting Daily Agentic Monitoring Pipeline...")
    db: Session = SessionLocal()
    
    try:
        # 1. Fetch active subscriptions to process
        if subscription_id:
            subscriptions = db.query(UserSubscription).filter(UserSubscription.id == subscription_id).all()
        elif force_send_email:
            subscriptions = db.query(UserSubscription).filter(UserSubscription.email == force_send_email).all()
        else:
            subscriptions = db.query(UserSubscription).filter(UserSubscription.is_active == True).all()

        if not subscriptions:
            logger.info("No active subscriptions found to process.")
            return {"success": True, "message": "No subscriptions to process."}

        # 2. Iterate and process each subscriber's portfolio
        results = []
        for sub in subscriptions:
            email = sub.email
            portfolio = sub.portfolio
            
            if not portfolio or not portfolio.holdings_json:
                logger.warning(f"No portfolio registered for subscriber {email}. Skipping.")
                continue

            holdings_list = portfolio.holdings_json
            logger.info(f"Processing monitoring pipeline for {email} with {len(holdings_list)} holdings...")
            
            # Convert holdings to pandas DataFrame for analysis
            df = pd.DataFrame(holdings_list)
            
            # Use custom subscriber model & key, or fallback to server env variables
            sub_model = sub.model or os.getenv("DEFAULT_MODEL", "gpt-4o-mini")
            sub_api_key = sub.api_key or (os.getenv("GEMINI_API_KEY") if "gemini" in sub_model.lower() else os.getenv("OPENAI_API_KEY"))
            
            analyzer = PortfolioAnalyzer(
                model=sub_model,
                api_key=sub_api_key
            )
            
            # Fetch local allocations
            allocations = analyzer.calculate_allocations(df)
            total_value = allocations["total_value"]
            
            # Fetch stock-specific headlines
            tickers = [h.get("Ticker", "") for h in holdings_list]
            aggregated_news = news_service.get_portfolio_news(tickers)
            
            # Format news in readable context for LLM reasoning
            news_context_str = ""
            for ticker, articles in aggregated_news.items():
                news_context_str += f"\n--- {ticker} Stock News ---\n"
                for idx, art in enumerate(articles, 1):
                    news_context_str += f"[{idx}] {art['headline']} (Source: {art['source']}, Date: {art['pubDate']})\n"

            # Execute specialized daily advisor analysis with LLM
            report = generate_ai_daily_report(analyzer, df, allocations, news_context_str)
            
            # 3. Store report in history
            db_report = DailyReport(
                subscription_id=sub.id,
                report_json=report
            )
            db.add(db_report)
            db.commit()
            
            # 4. Dispatch Email Report
            email_sent = email_service.send_daily_report(email, report, total_value)
            
            results.append({
                "email": email,
                "success": True,
                "email_sent": email_sent,
                "report": report
            })
            
        return {"success": True, "processed": results}
        
    except Exception as e:
        logger.error(f"Critical error in daily monitoring pipeline: {str(e)}")
        return {"success": False, "error": str(e)}
    finally:
        db.close()

def generate_ai_daily_report(analyzer: PortfolioAnalyzer, df: pd.DataFrame, allocations: Dict[str, Any], news_context: str) -> Dict[str, Any]:
    """
    Invokes the LLM Reasoning Layer to analyze how today's stock-specific
    news affects the user's specific holdings.
    """
    if not analyzer.client:
        return {
            "health_score": allocations["calculated_health_score"],
            "risk_score": allocations["calculated_risk_score"],
            "executive_summary": "Please configure a valid API key to enable daily news impact reasoning.",
            "top_risks": ["API Key Missing"],
            "positive_aspects": ["Local allocations calculated successfully"],
            "insights": []
        }

    portfolio_summary = df[["Asset Name", "Ticker", "Sector", "Current Value", "Beta"]].to_markdown(index=False)
    
    system_prompt = """You are a senior portfolio intelligence agent. You MUST respond with ONLY a raw JSON object. Do not wrap it in markdown code blocks or add extra text.
Your JSON must strictly match this schema:
{
  "health_score": number (1-100),
  "risk_score": number (1.0-10.0),
  "executive_summary": "A 2-3 sentence overview of how today's aggregated news affects this portfolio specifically",
  "top_risks": ["Risk 1", "Risk 2"],
  "positive_aspects": ["Highlight 1", "Highlight 2"],
  "insights": [
    {
      "type": "warning" | "positive" | "info",
      "title": "Short Title",
      "description": "Explanation of how a specific news event affects a specific ticker and what action the user should consider"
    }
  ]
}
"""

    user_prompt = f"""
Analyze how today's market news impacts this specific investment portfolio.

### 1. Portfolio Allocation Details
{portfolio_summary}
Total Value: ₹{allocations['total_value']:.2f}
Calculated Volatility Risk: {allocations['calculated_risk_score']}/10
Calculated Health: {allocations['calculated_health_score']}/100

### 2. Today's Relevant Stock News
{news_context}

Compare the news against the holdings. Synthesize the risks and positives. If a news item has high volatility implications, detail it as a "warning" insight. If a company is reporting solid updates, detail it as a "positive" insight. Make sure all insights directly reference specific tickers.
Provide the structured JSON output.
"""

    try:
        response = analyzer.client.chat.completions.create(
            model=analyzer.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.3
        )
        
        raw_content = response.choices[0].message.content.strip()
        
        # Clean up markdown code blocks if any
        if raw_content.startswith("```json"):
            raw_content = raw_content[7:]
        if raw_content.startswith("```"):
            raw_content = raw_content[3:]
        if raw_content.endswith("```"):
            raw_content = raw_content[:-3]
            
        parsed_json = json.loads(raw_content.strip())
        return parsed_json
        
    except Exception as e:
        logger.error(f"Failed to generate daily AI advice: {str(e)}")
        return {
            "health_score": allocations["calculated_health_score"],
            "risk_score": allocations["calculated_risk_score"],
            "executive_summary": f"Failed to synthesize news. Technical error: {str(e)}",
            "top_risks": ["Daily LLM reasoning failed"],
            "positive_aspects": [],
            "insights": []
        }

def start_scheduler():
    """
    Registers and boots the background daily monitoring scheduler.
    Default schedule is every day at 8:00 AM.
    """
    if not scheduler.running:
        # Schedule the monitoring task daily at 8:00 AM
        scheduler.add_job(
            run_daily_monitoring_job,
            trigger='cron',
            hour=8,
            minute=0,
            id='daily_monitoring_pipeline',
            replace_existing=True
        )
        scheduler.start()
        logger.info("Background AsyncIOScheduler started successfully. Scheduled 'daily_monitoring_pipeline' for 8:00 AM daily.")

def stop_scheduler():
    """
    Stops the background scheduler.
    """
    if scheduler.running:
        scheduler.shutdown()
        logger.info("Background AsyncIOScheduler shut down.")
