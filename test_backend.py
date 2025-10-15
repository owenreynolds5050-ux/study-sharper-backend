#!/usr/bin/env python3
"""
Quick Backend Test Script
Tests if backend is running and can connect to services
"""

import sys
import requests
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

BACKEND_URL = "http://127.0.0.1:8000"

def test_backend_health():
    """Test if backend is running"""
    try:
        response = requests.get(f"{BACKEND_URL}/health", timeout=5)
        if response.status_code == 200:
            print("✅ Backend is running")
            print(f"   Response: {response.json()}")
            return True
        else:
            print(f"❌ Backend returned status {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print("❌ Backend is NOT running")
        print("   Start it with: uvicorn app.main:app --reload")
        return False
    except Exception as e:
        print(f"❌ Error connecting to backend: {e}")
        return False

def test_folders_api():
    """Test folders API health"""
    try:
        response = requests.get(f"{BACKEND_URL}/api/folders/health", timeout=5)
        if response.status_code == 200:
            print("✅ Folders API is healthy")
            return True
        else:
            print(f"❌ Folders API returned status {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Folders API error: {e}")
        return False

def test_ai_chat_health():
    """Test AI chat health"""
    try:
        response = requests.get(f"{BACKEND_URL}/api/ai/chat/health", timeout=5)
        if response.status_code == 200:
            print("✅ AI Chat API is healthy")
            return True
        else:
            print(f"❌ AI Chat API returned status {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ AI Chat API error: {e}")
        return False

def test_environment():
    """Test environment configuration"""
    try:
        from app.core.config import SUPABASE_URL, SUPABASE_KEY, OPENROUTER_API_KEY
        
        issues = []
        if not SUPABASE_URL or "your-project" in SUPABASE_URL:
            issues.append("SUPABASE_URL not configured")
        if not SUPABASE_KEY or "your-service-role" in SUPABASE_KEY:
            issues.append("SUPABASE_SERVICE_ROLE_KEY not configured")
        if not OPENROUTER_API_KEY or "your-openrouter" in OPENROUTER_API_KEY:
            issues.append("OPENROUTER_API_KEY not configured")
        
        if issues:
            print("❌ Environment issues:")
            for issue in issues:
                print(f"   - {issue}")
            return False
        else:
            print("✅ Environment variables configured")
            return True
    except Exception as e:
        print(f"❌ Error checking environment: {e}")
        return False

def main():
    print("=" * 70)
    print("Backend Test Script")
    print("=" * 70)
    print()
    
    # Test 1: Environment
    print("📋 Testing Environment Configuration...")
    print("-" * 70)
    env_ok = test_environment()
    print()
    
    # Test 2: Backend running
    print("📋 Testing Backend Connection...")
    print("-" * 70)
    backend_ok = test_backend_health()
    print()
    
    if not backend_ok:
        print("⚠️  Backend is not running. Start it with:")
        print("   cd Study_Sharper_Backend")
        print("   uvicorn app.main:app --reload")
        return 1
    
    # Test 3: API endpoints
    print("📋 Testing API Endpoints...")
    print("-" * 70)
    folders_ok = test_folders_api()
    ai_ok = test_ai_chat_health()
    print()
    
    # Summary
    print("=" * 70)
    print("Summary")
    print("=" * 70)
    print(f"{'✅' if env_ok else '❌'} Environment Configuration")
    print(f"{'✅' if backend_ok else '❌'} Backend Running")
    print(f"{'✅' if folders_ok else '❌'} Folders API")
    print(f"{'✅' if ai_ok else '❌'} AI Chat API")
    print("=" * 70)
    
    if all([env_ok, backend_ok, folders_ok, ai_ok]):
        print("\n🎉 All tests passed! Backend is ready.")
        return 0
    else:
        print("\n⚠️  Some tests failed. Check the errors above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
