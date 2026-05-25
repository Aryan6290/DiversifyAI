import os
import pandas as pd
from kiteconnect import KiteConnect
import logging

class KiteIntegration:
    def __init__(self):
        self.api_key = os.getenv("KITE_API_KEY")
        self.api_secret = os.getenv("KITE_API_SECRET")
        if not self.api_key or not self.api_secret:
            logging.warning("KITE_API_KEY or KITE_API_SECRET not found in environment variables.")
        
        self.kite = KiteConnect(api_key=self.api_key)

    def get_login_url(self) -> str:
        """Returns the Kite Connect login URL."""
        if not self.api_key:
            raise ValueError("Kite API key is missing. Cannot generate login URL.")
        return self.kite.login_url()

    def generate_session(self, request_token: str) -> str:
        """
        Exchanges the request_token for an access_token.
        Sets the access_token in the kite instance and returns it.
        """
        try:
            data = self.kite.generate_session(request_token, api_secret=self.api_secret)
            access_token = data["access_token"]
            self.kite.set_access_token(access_token)
            return access_token
        except Exception as e:
            logging.error(f"Failed to generate Kite session: {str(e)}")
            raise

    def set_access_token(self, access_token: str):
        """Allows setting an existing access token."""
        self.kite.set_access_token(access_token)

    def fetch_holdings(self) -> list:
        """Fetches and normalizes the user's holdings."""
        try:
            holdings = self.kite.holdings()
            
            normalized = []
            for h in holdings:
                normalized.append({
                    "ticker": h.get("tradingsymbol", "UNKNOWN"),
                    "quantity": h.get("quantity", 0),
                    "avg_price": h.get("average_price", 0.0),
                    "current_price": h.get("last_price", 0.0)
                })
            
            return normalized
        except Exception as e:
            logging.error(f"Failed to fetch Kite holdings: {str(e)}")
            raise

    def to_analyzer_format(self, normalized_holdings: list) -> pd.DataFrame:
        """
        Converts the normalized holdings to the DataFrame format 
        expected by the PortfolioAnalyzer.
        Expected columns: ["Asset Name", "Ticker", "Asset Type", "Sector", "Current Value", "Currency"]
        """
        data = []
        for h in normalized_holdings:
            current_value = h["quantity"] * h["current_price"]
            # Exclude zero-value holdings if any
            if current_value > 0:
                data.append({
                    "Asset Name": h["ticker"],
                    "Ticker": h["ticker"],
                    "Asset Type": "Equity", # Defaulting to Equity
                    "Sector": "Unclassified", # Kite doesn't provide sector
                    "Current Value": current_value,
                    "Currency": "INR"
                })
        
        return pd.DataFrame(data)
