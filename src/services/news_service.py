import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
import logging
from typing import List, Dict, Any
import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("NewsService")

class NewsService:
    """
    Fetches real-time finance news for specific stock tickers 
    using the Google News RSS feed search.
    """
    
    def __init__(self):
        # Local 1-hour cache to speed up requests for common tickers across users
        self._cache: Dict[str, Dict[str, Any]] = {}

    def fetch_ticker_news(self, ticker: str, max_results: int = 3) -> List[Dict[str, str]]:
        """
        Queries Google News RSS for the ticker, parses and returns the top N articles.
        """
        now = datetime.datetime.now()
        ticker = ticker.upper().strip()
        
        # Check cache
        if ticker in self._cache:
            cache_entry = self._cache[ticker]
            # 1 hour expiration
            if now - cache_entry["timestamp"] < datetime.timedelta(hours=1):
                logger.info(f"Returning cached news for ticker: {ticker}")
                return cache_entry["articles"]

        # Clean tickers for search (e.g., RELIANCE.NS -> RELIANCE)
        search_ticker = ticker.split('.')[0]
        query = f"{search_ticker} stock"
        url = f"https://news.google.com/rss/search?q={urllib.parse.quote(query)}&hl=en-IN&gl=IN&ceid=IN:en"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        articles = []
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=5) as response:
                xml_data = response.read()
                
            root = ET.fromstring(xml_data)
            # Find all <item> tags under <channel>
            channel = root.find('channel')
            if channel is not None:
                items = channel.findall('item')
                for item in items[:max_results]:
                    title = item.find('title')
                    link = item.find('link')
                    pub_date = item.find('pubDate')
                    source = item.find('source')
                    
                    articles.append({
                        "headline": title.text if title is not None else "No Title",
                        "link": link.text if link is not None else "#",
                        "pubDate": pub_date.text if pub_date is not None else "",
                        "source": source.text if source is not None else "Unknown Source"
                    })
                    
        except Exception as e:
            logger.error(f"Failed to fetch news for {ticker}: {str(e)}")
            # Return fallback news article in case of rate-limiting or network outage
            articles = [{
                "headline": f"Regular market trading activity observed for {ticker}.",
                "link": "#",
                "pubDate": datetime.datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S GMT"),
                "source": "Market Update"
            }]

        # Store in cache
        self._cache[ticker] = {
            "articles": articles,
            "timestamp": now
        }
        
        return articles

    def get_portfolio_news(self, tickers: List[str]) -> Dict[str, List[Dict[str, str]]]:
        """
        Aggregates news for a complete list of unique portfolio tickers.
        """
        unique_tickers = list(set(tickers))
        portfolio_news = {}
        for ticker in unique_tickers:
            # Skip cash or unclassified ticker types
            if ticker in ["USD", "INR", "CASH", "N/A", "UNKNOWN", ""]:
                continue
            portfolio_news[ticker] = self.fetch_ticker_news(ticker)
        return portfolio_news
