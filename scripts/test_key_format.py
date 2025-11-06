import os
import base64
from dotenv import load_dotenv

load_dotenv(".env.local")
key = os.getenv("TOKEN_ENCRYPTION_KEY")

if not key:
    print("❌ TOKEN_ENCRYPTION_KEY not set")
    exit(1)

print(f"Key: {key}")
print(f"Length: {len(key)}")

# Try decoding
try:
    # Add padding if needed
    key_str = key.strip()
    missing_padding = len(key_str) % 4
    if missing_padding:
        key_str += "=" * (4 - missing_padding)

    decoded = base64.urlsafe_b64decode(key_str)
    print(f"Decoded length: {len(decoded)} bytes")
    print(f"✅ Key is valid (32 bytes required)")
except Exception as e:
    print(f"❌ Error decoding: {e}")
