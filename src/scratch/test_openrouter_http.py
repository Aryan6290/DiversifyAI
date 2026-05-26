import sys
from openai import OpenAI

client = OpenAI(
    api_key="AIzaSyTestKey",
    base_url="https://openrouter.ai/api/v1"
)

try:
    response = client.chat.completions.create(
        model="google/gemini-2.5-flash",
        messages=[
            {"role": "user", "content": "Hello"}
        ]
    )
    print("SUCCESS:", response)
except Exception as e:
    print("ERROR TYPE:", type(e))
    print("ERROR MSG:", str(e))
