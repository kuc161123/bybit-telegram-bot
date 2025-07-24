#!/usr/bin/env python3
"""
Test network connectivity
"""
import asyncio
import httpx
import socket
import ssl

async def test_network():
    """Test network connectivity"""
    print("🔍 Testing network connectivity...")
    
    # Test DNS resolution
    try:
        print("\n1️⃣ Testing DNS resolution...")
        ip = socket.gethostbyname("api.telegram.org")
        print(f"✅ DNS resolution successful: api.telegram.org -> {ip}")
    except Exception as e:
        print(f"❌ DNS resolution failed: {e}")
    
    # Test HTTPS connection
    try:
        print("\n2️⃣ Testing HTTPS connection to Telegram...")
        async with httpx.AsyncClient() as client:
            response = await client.get("https://api.telegram.org")
            print(f"✅ HTTPS connection successful: Status {response.status_code}")
    except Exception as e:
        print(f"❌ HTTPS connection failed: {e}")
    
    # Test SSL/TLS
    try:
        print("\n3️⃣ Testing SSL/TLS...")
        context = ssl.create_default_context()
        print(f"✅ SSL context created successfully")
        print(f"   Protocol: {context.protocol}")
        print(f"   Verify mode: {context.verify_mode}")
    except Exception as e:
        print(f"❌ SSL/TLS test failed: {e}")
    
    # Test Bybit API
    try:
        print("\n4️⃣ Testing Bybit API connection...")
        async with httpx.AsyncClient() as client:
            response = await client.get("https://api.bybit.com/v5/market/time")
            print(f"✅ Bybit API connection successful: {response.json()['retMsg']}")
    except Exception as e:
        print(f"❌ Bybit API connection failed: {e}")
    
    print("\n✅ Network connectivity test completed")

if __name__ == "__main__":
    asyncio.run(test_network())