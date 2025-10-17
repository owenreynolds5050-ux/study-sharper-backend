"""
Verification script to ensure all memory optimizations are in place.
Run this before deployment to verify everything is configured correctly.

Usage: python verify_optimizations.py
"""

import sys
import os
from pathlib import Path

def check_file_exists(filepath, description):
    """Check if a file exists"""
    if Path(filepath).exists():
        print(f"✅ {description}: {filepath}")
        return True
    else:
        print(f"❌ {description} MISSING: {filepath}")
        return False

def check_file_contains(filepath, search_string, description):
    """Check if a file contains a specific string"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            if search_string in content:
                print(f"✅ {description}")
                return True
            else:
                print(f"❌ {description} NOT FOUND in {filepath}")
                return False
    except Exception as e:
        print(f"❌ Error reading {filepath}: {e}")
        return False

def verify_phase_1():
    """Verify Phase 1: Cache & SSE optimizations"""
    print("\n" + "="*60)
    print("PHASE 1: Cache & SSE Memory Fixes")
    print("="*60)
    
    checks = []
    
    # Check cache.py
    checks.append(check_file_contains(
        "app/agents/cache.py",
        "MAX_MESSAGES = 10",
        "Cache: MAX_MESSAGES constant (should be max_items)"
    ))
    checks.append(check_file_contains(
        "app/agents/cache.py",
        "OrderedDict",
        "Cache: Using OrderedDict for LRU"
    ))
    checks.append(check_file_contains(
        "app/agents/cache.py",
        "_evict_oldest",
        "Cache: Eviction method exists"
    ))
    checks.append(check_file_contains(
        "app/agents/cache.py",
        "estimated_size_mb",
        "Cache: Memory tracking in get_stats()"
    ))
    
    # Check sse.py
    checks.append(check_file_contains(
        "app/agents/sse.py",
        "maxsize=",
        "SSE: Bounded queues"
    ))
    checks.append(check_file_contains(
        "app/agents/sse.py",
        "cleanup_stale_connections",
        "SSE: Cleanup method exists"
    ))
    checks.append(check_file_contains(
        "app/agents/sse.py",
        "last_activity",
        "SSE: Activity tracking"
    ))
    
    # Check main.py
    checks.append(check_file_contains(
        "app/main.py",
        "start_sse_cleanup",
        "Main: SSE cleanup task exists"
    ))
    checks.append(check_file_contains(
        "app/main.py",
        "@app.on_event(\"startup\")",
        "Main: Startup event handler"
    ))
    
    return all(checks)

def verify_phase_4():
    """Verify Phase 4: Conversation history limits"""
    print("\n" + "="*60)
    print("PHASE 4: Conversation History Optimization")
    print("="*60)
    
    checks = []
    
    checks.append(check_file_contains(
        "app/agents/context/conversation_agent.py",
        "MAX_MESSAGES = 10",
        "Conversation: MAX_MESSAGES constant"
    ))
    checks.append(check_file_contains(
        "app/agents/context/conversation_agent.py",
        "MAX_CONTENT_MESSAGES = 5",
        "Conversation: MAX_CONTENT_MESSAGES constant"
    ))
    checks.append(check_file_contains(
        "app/agents/context/conversation_agent.py",
        "MAX_CONTENT_LENGTH = 200",
        "Conversation: MAX_CONTENT_LENGTH constant"
    ))
    checks.append(check_file_contains(
        "app/agents/context/conversation_agent.py",
        "min(requested_limit, self.MAX_MESSAGES)",
        "Conversation: Hard cap enforcement"
    ))
    checks.append(check_file_contains(
        "app/agents/context/conversation_agent.py",
        "id, role, created_at",
        "Conversation: Metadata-first loading"
    ))
    
    return all(checks)

def verify_phase_6():
    """Verify Phase 6: Render config and testing"""
    print("\n" + "="*60)
    print("PHASE 6: Render Configuration & Testing")
    print("="*60)
    
    checks = []
    
    # Check render.yaml
    checks.append(check_file_contains(
        "render.yaml",
        "gunicorn",
        "Render: Using gunicorn"
    ))
    checks.append(check_file_contains(
        "render.yaml",
        "--workers 2",
        "Render: 2 workers configured"
    ))
    checks.append(check_file_contains(
        "render.yaml",
        "--max-requests",
        "Render: Auto-restart configured"
    ))
    checks.append(check_file_contains(
        "render.yaml",
        "healthCheckPath",
        "Render: Health check configured"
    ))
    
    # Check requirements.txt
    checks.append(check_file_contains(
        "requirements.txt",
        "gunicorn",
        "Requirements: gunicorn included"
    ))
    
    # Check test files exist
    checks.append(check_file_exists(
        "test_memory_leaks.py",
        "Tests: Memory leak test suite"
    ))
    checks.append(check_file_exists(
        "load_test.py",
        "Tests: Load testing script"
    ))
    
    return all(checks)

def verify_all():
    """Run all verifications"""
    print("\n" + "="*60)
    print("MEMORY OPTIMIZATION VERIFICATION")
    print("="*60)
    
    phase1 = verify_phase_1()
    phase4 = verify_phase_4()
    phase6 = verify_phase_6()
    
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    
    if phase1:
        print("✅ Phase 1: Cache & SSE optimizations")
    else:
        print("❌ Phase 1: Issues found")
    
    if phase4:
        print("✅ Phase 4: Conversation history limits")
    else:
        print("❌ Phase 4: Issues found")
    
    if phase6:
        print("✅ Phase 6: Render config & testing")
    else:
        print("❌ Phase 6: Issues found")
    
    print("="*60)
    
    if phase1 and phase4 and phase6:
        print("\n🎉 ALL OPTIMIZATIONS VERIFIED!")
        print("✅ Ready for deployment")
        print("\nNext steps:")
        print("1. Run tests: pytest test_memory_leaks.py -v")
        print("2. Run load test: python load_test.py")
        print("3. Commit changes: git add . && git commit")
        print("4. Deploy: git push origin main")
        return 0
    else:
        print("\n⚠️  SOME CHECKS FAILED")
        print("Please review the errors above and fix before deploying.")
        return 1

if __name__ == "__main__":
    exit_code = verify_all()
    sys.exit(exit_code)
