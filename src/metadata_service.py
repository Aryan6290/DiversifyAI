import yfinance as yf
import pandas as pd
from typing import Dict, Any

class StockMetadataService:
    """
    Fetches real-world metadata for tickers to classify them automatically.
    Uses yfinance to pull sector, industry, market cap, and beta.
    """
    
    def __init__(self):
        # Cache to avoid duplicate network calls
        self._cache: Dict[str, Dict[str, Any]] = {}
        
        # Fallback mappings for Indian stocks if yfinance fails or doesn't have suffix
        self.fallback_sectors = {
            "RELIANCE": {"sector": "Energy", "industry": "Oil & Gas Integrated"},
            "ITC": {"sector": "Consumer Defensive", "industry": "Tobacco"},
            "SUZLON": {"sector": "Industrials", "industry": "Electrical Equipment & Parts"},
            "HDFCBANK": {"sector": "Financial Services", "industry": "Banks - Regional"},
            "TCS": {"sector": "Technology", "industry": "Information Technology Services"},
            "INFY": {"sector": "Technology", "industry": "Information Technology Services"}
        }

    def _format_ticker(self, ticker: str) -> str:
        """
        Attempts to format standard tickers for yfinance. 
        For Indian stocks, adds .NS if not present.
        """
        ticker = ticker.upper().strip()
        # Very simple heuristic: if it doesn't have a dot and is common in NSE, append .NS
        # Real-world logic would be more robust, checking exchanges.
        if "." not in ticker:
            ticker += ".NS"
        return ticker

    def get_metadata(self, raw_ticker: str, asset_name: str = "") -> Dict[str, Any]:
        """
        Fetch metadata. Returns a dict with sector, industry, market_cap, beta.
        """
        if raw_ticker in self._cache:
            return self._cache[raw_ticker]

        ticker = self._format_ticker(raw_ticker)
        
        metadata = {
            "sector": "Unclassified",
            "industry": "Unclassified",
            "marketCap": 0.0,
            "beta": 1.0
        }

        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            
            if info:
                metadata["sector"] = info.get("sector", metadata["sector"])
                metadata["industry"] = info.get("industry", metadata["industry"])
                metadata["marketCap"] = info.get("marketCap", metadata["marketCap"])
                metadata["beta"] = info.get("beta", metadata["beta"])
        except Exception as e:
            print(f"yfinance fetch failed for {ticker}: {e}")
            
        # Apply fallbacks if still Unclassified
        if metadata["sector"] == "Unclassified" and raw_ticker.upper() in self.fallback_sectors:
            fallback = self.fallback_sectors[raw_ticker.upper()]
            metadata["sector"] = fallback["sector"]
            metadata["industry"] = fallback["industry"]
            
        # If it's a mutual fund or ETF, sector might not be there directly
        if metadata["sector"] == "Unclassified" and ("FUND" in asset_name.upper() or "ETF" in asset_name.upper()):
            metadata["sector"] = "Funds & ETFs"
            metadata["industry"] = "Investment Fund"
            
        self._cache[raw_ticker] = metadata
        return metadata
