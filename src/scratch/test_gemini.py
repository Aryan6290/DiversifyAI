import sys
sys.path.append("/Users/aryanbarnwal/Projects/GenAI Project/Sample/src")

from analyzer import PortfolioAnalyzer

analyzer = PortfolioAnalyzer(model="gemini-2.5-flash", api_key="AIzaSyTest", base_url=None)
print("Base URL:", analyzer.base_url)
print("API Key:", analyzer.api_key)
print("Client Base URL:", analyzer.client.base_url if analyzer.client else None)
