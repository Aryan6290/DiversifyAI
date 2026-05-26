import requests
import json

# Fetch mock holdings to send
mock_holdings = [
    {"Asset Name": "Apple Inc.", "Ticker": "AAPL", "Asset Type": "Equity", "Sector": "Technology", "Current Value": 50000, "Currency": "INR"}
]

# Send request to local server
headers = {
    "X-Model": "gpt-4o-mini",
    "X-API-Key": "AIzaSyTestMockKey",
    "Content-Type": "application/json"
}

# We need an active session cookie to bypass the Depends(get_current_user_id) guard.
# Or we can test by printing out what analyzer resolved on the backend if we trigger it.
# Let's bypass login by logging in first statefully!
session = requests.Session()

# Let's check if we can signup/login a test account
login_data = {"email": "debug_user@test.com", "password": "DebugPassword123"}
session.post("http://localhost:8000/api/auth/signup", json=login_data)
session.post("http://localhost:8000/api/auth/login", json=login_data)

res = session.post(
    "http://localhost:8000/api/analyze_holdings",
    headers=headers,
    json={"holdings": mock_holdings}
)

print("STATUS CODE:", res.status_code)
print("RESPONSE BODY:", res.json())
