#!/usr/bin/env python3
"""Quick test of OpenAI connection"""

import os
from openai import OpenAI

# Test connection
api_key = os.getenv("OPENAI_API_KEY") or os.getenv("MRC_OPENAI_API_KEY")
print(f"API Key found: {api_key[:20]}..." if api_key else "No API key!")

client = OpenAI(api_key=api_key)

try:
    print("Testing OpenAI connection...")
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "Say 'hello' in one word"}],
        max_tokens=5,
    )
    print(f"✅ SUCCESS! Response: {response.choices[0].message.content}")
except Exception as e:
    print(f"❌ ERROR: {e}")
    import traceback

    traceback.print_exc()
