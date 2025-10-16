"""
API Test Script for Phase 1 Agent System
Tests the /api/ai/agent-test endpoint
"""

import requests
import json
import sys

# Backend URL (adjust if needed)
BASE_URL = "http://localhost:8000"
AGENT_TEST_ENDPOINT = f"{BASE_URL}/api/ai/agent-test"


def test_endpoint(test_name, payload):
    """Test a single endpoint call"""
    print(f"\n{'='*60}")
    print(f"TEST: {test_name}")
    print(f"{'='*60}")
    print(f"Request: {json.dumps(payload, indent=2)}")
    
    try:
        response = requests.post(
            AGENT_TEST_ENDPOINT,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        
        print(f"\nStatus Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Response: {json.dumps(data, indent=2)}")
            
            # Validate response structure
            assert "status" in data, "Missing 'status' field"
            assert "result" in data, "Missing 'result' field"
            assert "execution_time_ms" in data, "Missing 'execution_time_ms' field"
            
            if data["status"] == "success":
                print(f"\n✓ Test passed")
                print(f"  - Intent: {data['result'].get('intent')}")
                print(f"  - Execution time: {data['execution_time_ms']}ms")
                return True
            else:
                print(f"\n✗ Test failed: {data.get('error', 'Unknown error')}")
                return False
        else:
            print(f"✗ HTTP Error: {response.status_code}")
            print(f"Response: {response.text}")
            return False
            
    except requests.exceptions.ConnectionError:
        print(f"\n✗ Connection Error: Could not connect to {BASE_URL}")
        print("Make sure the backend server is running!")
        return False
    except Exception as e:
        print(f"\n✗ Error: {e}")
        return False


def run_tests():
    """Run all API tests"""
    print("="*60)
    print("PHASE 1 AGENT API TEST SUITE")
    print("="*60)
    print(f"Testing endpoint: {AGENT_TEST_ENDPOINT}")
    
    # Check if server is running
    try:
        health_response = requests.get(f"{BASE_URL}/health", timeout=5)
        if health_response.status_code == 200:
            print(f"✓ Backend server is running")
        else:
            print(f"⚠️  Backend server returned status {health_response.status_code}")
    except:
        print(f"\n✗ Cannot connect to backend at {BASE_URL}")
        print("Please start the backend server first:")
        print("  cd Study_Sharper_Backend")
        print("  python -m uvicorn app.main:app --reload")
        return False
    
    # Test cases
    tests = [
        (
            "Basic Chat Request",
            {
                "type": "chat",
                "user_id": "test-user-123",
                "message": "Hello, this is a test message"
            }
        ),
        (
            "Flashcard Generation Request",
            {
                "type": "chat",
                "user_id": "test-user-123",
                "message": "Create flashcards about biology"
            }
        ),
        (
            "Quiz Generation Request",
            {
                "type": "chat",
                "user_id": "test-user-123",
                "message": "Generate a quiz on chemistry"
            }
        ),
        (
            "Summary Request",
            {
                "type": "chat",
                "user_id": "test-user-123",
                "message": "Summarize my notes on physics"
            }
        ),
        (
            "Explicit Request Type",
            {
                "type": "flashcard_generation",
                "user_id": "test-user-123",
                "message": "Create cards for studying",
                "options": {"difficulty": "medium"}
            }
        ),
        (
            "Request with Session ID",
            {
                "type": "chat",
                "user_id": "test-user-123",
                "session_id": "session-abc-123",
                "message": "Continue our conversation"
            }
        ),
    ]
    
    results = []
    for test_name, payload in tests:
        result = test_endpoint(test_name, payload)
        results.append((test_name, result))
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    passed = sum(1 for _, result in results if result)
    failed = len(results) - passed
    
    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {test_name}")
    
    print(f"\nTotal: {passed}/{len(results)} tests passed")
    
    if failed == 0:
        print("\n🎉 All API tests passed! Agent endpoint is working correctly.")
    else:
        print(f"\n⚠️  {failed} test(s) failed.")
    
    return failed == 0


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
