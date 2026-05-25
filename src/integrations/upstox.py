import os
import requests
import pandas as pd
import logging
import urllib.parse

class UpstoxIntegration:
    def __init__(self):
        self.api_key = os.getenv("UPSTOX_API_KEY")
        self.api_secret = os.getenv("UPSTOX_API_SECRET")
        # Hardcoding the expected redirect URI to ensure consistency
        self.redirect_uri = "http://127.0.0.1:8000/api/auth/upstox/callback"
        
        if not self.api_key or not self.api_secret:
            logging.warning("UPSTOX_API_KEY or UPSTOX_API_SECRET not found in environment variables.")
        
        self.access_token = None

    def get_login_url(self) -> str:
        """Returns the Upstox OAuth2 login URL."""
        if not self.api_key:
            raise ValueError("Upstox API key is missing. Cannot generate login URL.")
        
        base_url = "https://api.upstox.com/v2/login/authorization/dialog"
        params = {
            "response_type": "code",
            "client_id": self.api_key,
            "redirect_uri": self.redirect_uri
        }
        query_string = urllib.parse.urlencode(params)
        return f"{base_url}?{query_string}"

    def generate_session(self, code: str) -> str:
        """Exchanges the auth code for an access token."""
        url = 'https://api.upstox.com/v2/login/authorization/token'
        headers = {
            'accept': 'application/json',
            'Api-Version': '2.0',
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        data = {
            'code': code,
            'client_id': self.api_key,
            'client_secret': self.api_secret,
            'redirect_uri': self.redirect_uri,
            'grant_type': 'authorization_code'
        }
        
        response = requests.post(url, headers=headers, data=data)
        if response.status_code != 200:
            error_msg = response.json().get('errors', [{'message': response.text}])[0]['message']
            raise ValueError(f"Upstox Token Error: {error_msg}")
            
        json_resp = response.json()
        self.access_token = json_resp.get("access_token")
        return self.access_token

    def fetch_holdings(self) -> list:
        """Fetches long-term holdings from Upstox API."""
        if not self.access_token:
            raise ValueError("Access token is missing. Please generate a session first.")
            
        url = 'https://api.upstox.com/v2/portfolio/long-term-holdings'
        headers = {
            'accept': 'application/json',
            'Api-Version': '2.0',
            'Authorization': f'Bearer {self.access_token}'
        }
        
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            raise ValueError(f"Failed to fetch holdings: {response.text}")
            
        data = response.json().get('data', [])
        
        normalized = []
        for h in data:
            normalized.append({
                "ticker": h.get("tradingsymbol", h.get("instrument_token", "UNKNOWN")),
                "quantity": h.get("quantity", 0),
                "avg_price": h.get("average_price", 0.0),
                "current_price": h.get("last_price", 0.0)
            })
        
        return normalized

    def to_analyzer_format(self, normalized_holdings: list) -> pd.DataFrame:
        """Converts normalized holdings to PortfolioAnalyzer format."""
        data = []
        for h in normalized_holdings:
            current_value = h["quantity"] * h["current_price"]
            if current_value > 0:
                data.append({
                    "Asset Name": h["ticker"],
                    "Ticker": h["ticker"],
                    "Asset Type": "Equity",
                    "Sector": "Unclassified",
                    "Current Value": current_value,
                    "Currency": "INR"
                })
        
        return pd.DataFrame(data)
