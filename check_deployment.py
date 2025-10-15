#!/usr/bin/env python3
"""
Deployment Readiness Check Script
Run this before deploying to catch configuration issues early
"""

import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

def check_env_file():
    """Check if .env file exists"""
    env_path = Path(__file__).parent / ".env"
    if not env_path.exists():
        print("❌ .env file not found")
        print("   Create one from .env.example: cp .env.example .env")
        return False
    print("✅ .env file exists")
    return True

def check_environment_variables():
    """Check critical environment variables"""
    from app.core.config import SUPABASE_URL, SUPABASE_KEY, OPENROUTER_API_KEY
    
    issues = []
    
    if not SUPABASE_URL or "your-project" in SUPABASE_URL:
        issues.append("SUPABASE_URL not configured")
    else:
        print(f"✅ SUPABASE_URL: {SUPABASE_URL[:30]}...")
    
    if not SUPABASE_KEY or "your-service-role" in SUPABASE_KEY:
        issues.append("SUPABASE_SERVICE_ROLE_KEY not configured")
    else:
        print(f"✅ SUPABASE_SERVICE_ROLE_KEY: {SUPABASE_KEY[:20]}...")
    
    if not OPENROUTER_API_KEY or "your-openrouter" in OPENROUTER_API_KEY:
        issues.append("OPENROUTER_API_KEY not configured")
    else:
        print(f"✅ OPENROUTER_API_KEY: {OPENROUTER_API_KEY[:20]}...")
    
    if issues:
        print("\n❌ Missing environment variables:")
        for issue in issues:
            print(f"   - {issue}")
        return False
    
    return True

def check_dependencies():
    """Check required Python packages"""
    required = [
        "fastapi",
        "uvicorn",
        "supabase",
        "pyjwt",
        "python-dotenv",
        "requests"
    ]
    
    missing = []
    for package in required:
        try:
            __import__(package.replace("-", "_"))
            print(f"✅ {package} installed")
        except ImportError:
            missing.append(package)
            print(f"❌ {package} not installed")
    
    # Check optional but recommended
    try:
        from sentence_transformers import SentenceTransformer
        print("✅ sentence-transformers installed (recommended)")
    except ImportError:
        print("⚠️  sentence-transformers not installed (will use API fallback)")
    
    if missing:
        print(f"\n❌ Install missing packages:")
        print(f"   pip install {' '.join(missing)}")
        return False
    
    return True

def check_supabase_connection():
    """Test Supabase connection"""
    try:
        from app.core.auth import get_supabase_client
        supabase = get_supabase_client()
        
        # Try a simple query
        response = supabase.table("profiles").select("id").limit(1).execute()
        print("✅ Supabase connection successful")
        return True
    except Exception as e:
        print(f"❌ Supabase connection failed: {str(e)[:100]}")
        return False

def check_openrouter_connection():
    """Test OpenRouter API"""
    try:
        from app.services.open_router import get_chat_completion
        
        response = get_chat_completion(
            messages=[{"role": "user", "content": "Hello"}],
            model="anthropic/claude-3.5-sonnet",
            max_tokens=10
        )
        print("✅ OpenRouter API connection successful")
        return True
    except Exception as e:
        print(f"❌ OpenRouter API failed: {str(e)[:100]}")
        return False

def main():
    print("=" * 70)
    print("StudySharper Backend - Deployment Readiness Check")
    print("=" * 70)
    print()
    
    checks = [
        ("Environment File", check_env_file),
        ("Environment Variables", check_environment_variables),
        ("Python Dependencies", check_dependencies),
        ("Supabase Connection", check_supabase_connection),
        ("OpenRouter API", check_openrouter_connection),
    ]
    
    results = []
    for name, check_func in checks:
        print(f"\n📋 Checking {name}...")
        print("-" * 70)
        try:
            result = check_func()
            results.append((name, result))
        except Exception as e:
            print(f"❌ Check failed with error: {e}")
            results.append((name, False))
    
    print("\n" + "=" * 70)
    print("Summary")
    print("=" * 70)
    
    all_passed = True
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {name}")
        if not result:
            all_passed = False
    
    print("=" * 70)
    
    if all_passed:
        print("\n🎉 All checks passed! Ready for deployment.")
        print("\nNext steps:")
        print("1. Commit your changes")
        print("2. Deploy backend to Render/Railway")
        print("3. Set environment variables in deployment platform")
        print("4. Update frontend BACKEND_API_URL")
        print("5. Deploy frontend to Vercel")
        return 0
    else:
        print("\n⚠️  Some checks failed. Please fix the issues above before deploying.")
        print("\nSee DEPLOYMENT_GUIDE.md for detailed instructions.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
