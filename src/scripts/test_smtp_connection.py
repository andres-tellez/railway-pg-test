#!/usr/bin/env python
"""
Test SMTP Connection (DEPRECATED)
==================================

⚠️  NOTE: SMTP support has been removed. This script is kept for reference only.
Email sending now requires SendGrid REST API (SENDGRID_API_KEY).

This script was used to diagnose SMTP connectivity issues on Railway.
Since Railway blocks SMTP ports, SendGrid REST API is the required method.

Usage:
    python src/scripts/test_smtp_connection.py
"""

import os
import sys
import socket
import ssl
from pathlib import Path
from dotenv import load_dotenv

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Load environment variables
env_local_path = project_root / ".env.local"
if env_local_path.exists():
    load_dotenv(env_local_path, override=True)
else:
    env_staging_path = project_root / ".env.staging"
    if env_staging_path.exists():
        load_dotenv(env_staging_path, override=True)

# SMTP Configuration
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))

print("=" * 80)
print("SMTP Connection Diagnostic Test")
print("=" * 80)
print(f"Target: {SMTP_HOST}:{SMTP_PORT}")
print()

# Test 1: DNS Resolution
print("Test 1: DNS Resolution...")
try:
    ip_address = socket.gethostbyname(SMTP_HOST)
    print(f"✅ DNS resolved: {SMTP_HOST} -> {ip_address}")
except socket.gaierror as e:
    print(f"❌ DNS resolution failed: {e}")
    sys.exit(1)

# Test 2: TCP Connection
print(f"\nTest 2: TCP Connection to {SMTP_HOST}:{SMTP_PORT}...")
try:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(10)  # 10 second timeout
    result = sock.connect_ex((SMTP_HOST, SMTP_PORT))
    sock.close()

    if result == 0:
        print(f"✅ TCP connection successful to {SMTP_HOST}:{SMTP_PORT}")
    else:
        print(f"❌ TCP connection failed: Error code {result}")
        print("   This suggests Railway is blocking outbound SMTP connections")
except socket.timeout:
    print(f"❌ Connection timeout (host unreachable or blocked)")
except Exception as e:
    print(f"❌ Connection failed: {e}")

# Test 3: Try port 465 (SSL) instead
print(f"\nTest 3: Testing alternative port 465 (SSL)...")
try:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(10)
    result = sock.connect_ex((SMTP_HOST, 465))
    sock.close()

    if result == 0:
        print(f"✅ TCP connection successful to {SMTP_HOST}:465")
        print(
            "   💡 Consider using port 465 with SSL instead of port 587 with STARTTLS"
        )
    else:
        print(f"❌ TCP connection failed to port 465: Error code {result}")
except Exception as e:
    print(f"❌ Connection test failed: {e}")

# Test 4: Check if SMTP credentials are configured
print(f"\nTest 4: SMTP Credentials...")
username = os.getenv("SMTP_USERNAME")
password = os.getenv("SMTP_PASSWORD")

if username and password:
    print(f"✅ Username configured: {username[:3]}***")
    print(f"✅ Password configured: {'*' * len(password)}")
else:
    print("❌ SMTP credentials not configured")
    print("   Set SMTP_USERNAME and SMTP_PASSWORD environment variables")

print("\n" + "=" * 80)
print("Recommendations:")
print("=" * 80)

if result != 0:
    print("1. Railway may be blocking outbound SMTP connections on port 587")
    print("2. Try using port 465 with SSL instead of port 587 with STARTTLS")
    print("3. Consider using an SMTP relay service (SendGrid, Mailgun, etc.)")
    print("4. Check Railway's network settings or contact Railway support")
else:
    print("✅ Network connectivity looks good!")
    print("   The issue might be with authentication or TLS configuration")
