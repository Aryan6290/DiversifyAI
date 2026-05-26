import sys
from openai import OpenAI

client = OpenAI(
    api_key="AIzaSyTestKey",
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
)

try:
    response = client.chat.completions.create(
        model="gemini-2.5-flash",
        messages=[
            {"role": "user", "content": "Hello"}
        ]
    )
    print("SUCCESS:", response)
except Exception as e:
    print("ERROR TYPE:", type(e))
    print("ERROR MSG:", str(e))
