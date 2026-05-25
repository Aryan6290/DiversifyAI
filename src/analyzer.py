import os
import json
import pandas as pd
from openai import OpenAI
from typing import Tuple, Dict, Any
from metadata_service import StockMetadataService

class PortfolioAnalyzer:
    """
    Handles parsing portfolio CSV files, computing basic metrics,
    and invoking dynamic GenAI models via the OpenAI SDK natively or 
    through OpenRouter (by changing the base_url).
    """

    REQUIRED_COLUMNS = ["Asset Name", "Ticker", "Asset Type", "Sector", "Current Value", "Currency"]

    def __init__(self, model: str = "gpt-4o-mini", api_key: str = None, base_url: str = None):
        """
        Initializes the analyzer with a specific model name and an optional OpenRouter/Proxy base_url.
        """
        self.model = model.strip()
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        self.base_url = base_url or os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")

        if not base_url and self.model.startswith("gpt"):
            self.base_url = "https://api.openai.com/v1"
            self.api_key = self.api_key or os.getenv("OPENAI_API_KEY")
            
        elif not base_url and self.model.startswith("gemini"):
            self.base_url = "https://generativelanguage.googleapis.com/v1beta/openai/"
            self.api_key = self.api_key or os.getenv("GEMINI_API_KEY")

        if self.api_key:
            self.client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url
            )
        else:
            self.client = None
            
        self.metadata_service = StockMetadataService()

    def load_portfolio(self, csv_input) -> pd.DataFrame:
        """
        Loads and validates the portfolio CSV file.
        Enriches 'Unclassified' sectors using StockMetadataService.
        """
        if isinstance(csv_input, str):
            if not os.path.exists(csv_input):
                raise FileNotFoundError(f"Portfolio file not found at: {csv_input}")

        try:
            df = pd.read_csv(csv_input)
        except Exception as e:
            raise ValueError(f"Failed to read CSV file: {str(e)}")

        df.columns = [col.strip() for col in df.columns]
        missing_cols = [col for col in self.REQUIRED_COLUMNS if col not in df.columns]
        if missing_cols:
            raise ValueError(f"Missing required columns in CSV: {missing_cols}")

        try:
            df["Current Value"] = pd.to_numeric(df["Current Value"])
        except Exception:
            raise ValueError("All entries in the 'Current Value' column must be numeric.")

        df = self.enrich_portfolio(df)
        return df

    def enrich_portfolio(self, df: pd.DataFrame) -> pd.DataFrame:
        if "Beta" not in df.columns:
            df["Beta"] = 1.0
        if "MarketCap" not in df.columns:
            df["MarketCap"] = 0.0

        for idx, row in df.iterrows():
            ticker = row.get("Ticker", "")
            asset_name = row.get("Asset Name", "")
            if pd.notna(ticker) and str(ticker).strip():
                meta = self.metadata_service.get_metadata(str(ticker), str(asset_name))
                
                # Update sector if missing or unclassified
                current_sector = str(row.get("Sector", "")).strip()
                if not current_sector or current_sector.lower() in ["unclassified", "unknown", "nan"]:
                    df.at[idx, "Sector"] = meta["sector"]
                    
                df.at[idx, "Beta"] = meta["beta"] if meta["beta"] is not None else 1.0
                df.at[idx, "MarketCap"] = meta["marketCap"] if meta["marketCap"] is not None else 0.0
        return df

    def _categorize_market_cap(self, mcap):
        if mcap >= 1e10: return "Large Cap"
        if mcap >= 2e9: return "Mid Cap"
        return "Small Cap"

    def _categorize_risk(self, beta):
        if beta > 1.2: return "High Volatility"
        if beta < 0.8: return "Low Volatility"
        return "Medium Volatility"

    def calculate_allocations(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Computes local summaries (Asset Type, Sector, Market Cap, Risk).
        """
        if "MarketCap" not in df.columns or "Beta" not in df.columns:
            df = self.enrich_portfolio(df)

        total_value = df["Current Value"].sum()
        if total_value <= 0:
            raise ValueError("Total portfolio value must be greater than 0.")

        def group_and_pct(group_by_col):
            if group_by_col not in df.columns:
                return pd.DataFrame()
            grouped = df.groupby(group_by_col)["Current Value"].sum().reset_index()
            grouped["Percentage"] = (grouped["Current Value"] / total_value) * 100
            return grouped.sort_values(by="Percentage", ascending=False)

        asset_type_group = group_and_pct("Asset Type")
        sector_group = group_and_pct("Sector")
        
        # Calculate derived allocations
        df["MarketCapCategory"] = df["MarketCap"].apply(self._categorize_market_cap)
        df["RiskCategory"] = df["Beta"].apply(self._categorize_risk)
        
        market_cap_group = group_and_pct("MarketCapCategory")
        risk_group = group_and_pct("RiskCategory")
        
        # Calculate a naive Risk Score (1-10) based on beta and concentration
        weighted_beta = (df["Beta"] * (df["Current Value"] / total_value)).sum()
        top_sector_pct = sector_group["Percentage"].iloc[0] if not sector_group.empty else 0
        top_asset_pct = (df["Current Value"].max() / total_value) * 100
        
        # Base risk from beta (beta 1.0 = score 5, 1.5 = 7.5, etc.)
        risk_score = min(max(weighted_beta * 5, 1), 10)
        # Add concentration penalties
        if top_sector_pct > 40: risk_score += 1.0
        if top_asset_pct > 20: risk_score += 1.0
        risk_score = min(round(risk_score, 1), 10.0)

        # Calculate a naive Health Score (1-100)
        health_score = 100
        # Penalties for over-concentration
        if top_sector_pct > 40: health_score -= (top_sector_pct - 40)
        if top_asset_pct > 15: health_score -= (top_asset_pct - 15) * 2
        # Penalty for lacking asset type diversification
        if len(asset_type_group) == 1: health_score -= 15
        
        health_score = max(min(round(health_score), 100), 0)

        return {
            "total_value": total_value,
            "asset_type_breakdown": asset_type_group,
            "sector_breakdown": sector_group,
            "market_cap_breakdown": market_cap_group,
            "risk_breakdown": risk_group,
            "calculated_risk_score": risk_score,
            "calculated_health_score": health_score,
            "benchmark_comparison": {
                "benchmark_name": "NIFTY 50",
                "portfolio_return": "14.2%", # Mock values for simulation
                "benchmark_return": "12.0%",
                "outperformance": "2.2%"
            }
        }

    def generate_diversification_report(self, df: pd.DataFrame, allocations: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sends the portfolio summary to the chosen model and requests a structured JSON response.
        """
        if not self.client:
            return {
                "error": "API Key is missing.",
                "insights": [],
                "top_risks": [],
                "positive_aspects": [],
                "health_score": allocations["calculated_health_score"],
                "risk_score": allocations["calculated_risk_score"],
                "executive_summary": "Please supply an API key to enable GenAI analysis."
            }

        portfolio_summary_str = df[["Asset Name", "Ticker", "Sector", "Current Value", "Beta"]].to_markdown(index=False)
        sector_str = allocations["sector_breakdown"].to_markdown(index=False)
        
        system_prompt = """You are an expert financial advisor. You MUST respond with ONLY a raw JSON object. Do not wrap it in markdown block quotes (```json) or add any other text.
Your JSON must strictly match this schema:
{
  "health_score": number (1-100),
  "risk_score": number (1.0-10.0),
  "executive_summary": "A 2-3 sentence overview",
  "top_risks": ["Risk 1", "Risk 2", "Risk 3"],
  "positive_aspects": ["Positive 1", "Positive 2"],
  "insights": [
    {
      "type": "warning" | "positive" | "info",
      "title": "Short Title",
      "description": "Detailed explanation mentioning specific tickers or %"
    }
  ]
}
"""

        user_prompt = f"""
Analyze this portfolio:

### 1. Portfolio Data
{portfolio_summary_str}

### 2. Sector Breakdown
{sector_str}

Total Value: {allocations['total_value']:.2f}
Calculated Baseline Risk: {allocations['calculated_risk_score']}/10
Calculated Baseline Health: {allocations['calculated_health_score']}/100

Please provide the structured JSON analysis. Adjust the baseline scores slightly if you see specific qualitative risks. Provide at least 3 actionable insights (warnings/positives).
"""

        try:
            # We enforce JSON output if supported by the model, but to be safe across models, 
            # we prompt heavily and parse robustly.
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.2,
                response_format={ "type": "json_object" } if "gpt" in self.model else None
            )
            
            raw_content = response.choices[0].message.content.strip()
            
            # Clean up markdown code blocks if the model ignored the system prompt
            if raw_content.startswith("```json"):
                raw_content = raw_content[7:]
            if raw_content.startswith("```"):
                raw_content = raw_content[3:]
            if raw_content.endswith("```"):
                raw_content = raw_content[:-3]
                
            parsed_json = json.loads(raw_content.strip())
            
            # Merge with defaults to ensure schema is intact
            return {
                "health_score": parsed_json.get("health_score", allocations["calculated_health_score"]),
                "risk_score": parsed_json.get("risk_score", allocations["calculated_risk_score"]),
                "executive_summary": parsed_json.get("executive_summary", "Analysis completed."),
                "top_risks": parsed_json.get("top_risks", []),
                "positive_aspects": parsed_json.get("positive_aspects", []),
                "insights": parsed_json.get("insights", [])
            }

        except Exception as e:
            return {
                "error": str(e),
                "insights": [],
                "top_risks": ["Failed to generate GenAI risks."],
                "positive_aspects": [],
                "health_score": allocations["calculated_health_score"],
                "risk_score": allocations["calculated_risk_score"],
                "executive_summary": f"API Error: {str(e)}"
            }

    def chat(self, df: pd.DataFrame, message: str, history: list = None) -> str:
        """
        Handles interactive Q&A about the portfolio.
        """
        if not self.client:
            return "API Key missing. Cannot answer questions."
            
        portfolio_summary_str = df[["Asset Name", "Ticker", "Sector", "Current Value", "Beta"]].to_markdown(index=False)
        
        messages = [
            {"role": "system", "content": "You are a helpful AI financial assistant. You are answering questions about the user's specific investment portfolio. Keep your answers concise, professional, and directly reference their holdings when relevant."}
        ]
        
        if history:
            for msg in history:
                messages.append(msg)
                
        # Inject context into the latest user message
        context = f"\n\n[PORTFOLIO CONTEXT]\n{portfolio_summary_str}"
        messages.append({"role": "user", "content": message + context})

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.4
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"Error connecting to AI: {str(e)}"
