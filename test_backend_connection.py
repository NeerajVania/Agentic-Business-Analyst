#!/usr/bin/env python
"""Quick diagnostic to test backend connection and endpoint health."""

import sys
import time
import requests
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent))

def test_health():
    """Test if backend is reachable on any common port."""
    url = "http://127.0.0.1:8000/health"
    print(f"Testing: {url}")
    
    for attempt in range(1, 4):
        try:
            resp = requests.get(url, timeout=2)
            if resp.status_code == 200:
                print(f"✓ Backend is healthy: {resp.json()}")
                return True
            else:
                print(f"✗ Backend returned {resp.status_code}: {resp.text}")
                return False
        except requests.exceptions.ConnectionError as e:
            print(f"Attempt {attempt}/3: Connection refused — {e}")
            if attempt < 3:
                print("  Retrying in 2 seconds...")
                time.sleep(2)
        except Exception as e:
            print(f"✗ Error: {e}")
            return False
    
    print("\n✗ Could not connect to backend. Troubleshooting steps:")
    print("  1. Verify backend is running: python -m uvicorn backend.main:app --reload --host 0.0.0.0")
    print("  2. Check if port 8000 is in use: lsof -i :8000 (Linux/Mac) or netstat -tuln (Windows)")
    print("  3. Try connecting with: curl http://127.0.0.1:8000/health")
    return False

def test_upload_endpoint():
    """Test if upload endpoint is registered."""
    import io
    from typing import BinaryIO
    
    url = "http://127.0.0.1:8000/upload/multi"
    print(f"\nTesting: {url}")
    
    try:
        # Create a minimal CSV file in memory
        csv_data = b"name,age\nAlice,30\nBob,25"
        files = [("files", ("test.csv", io.BytesIO(csv_data), "text/csv"))]
        
        resp = requests.post(url, files=files, timeout=5)
        print(f"Status: {resp.status_code}")
        print(f"Response: {resp.json() if resp.headers.get('content-type') == 'application/json' else resp.text[:200]}")
        
        if resp.status_code in (200, 201, 422):  # 422 is validation error (expected if auth is required)
            print("✓ Endpoint is reachable")
            return True
        else:
            print(f"✗ Unexpected status code: {resp.status_code}")
            return False
            
    except requests.exceptions.ConnectionError as e:
        print(f"✗ Connection refused: {e}")
        return False
    except Exception as e:
        print(f"✗ Error: {e}")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("Backend Connectivity Test")
    print("=" * 60)
    
    health_ok = test_health()
    if health_ok:
        test_upload_endpoint()
    
    sys.exit(0 if health_ok else 1)
