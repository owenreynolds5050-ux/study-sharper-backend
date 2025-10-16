"""
Test Script for Phase 1 Agent System
Tests the new agent infrastructure without affecting existing functionality
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from app.agents.orchestrator import MainOrchestrator
from app.agents.models import AgentRequest, RequestType
from app.agents.cache import cache
from app.agents.base import AgentType
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


async def test_base_imports():
    """Test 1: Verify all imports work"""
    print("\n" + "="*60)
    print("TEST 1: Base Imports")
    print("="*60)
    
    try:
        from app.agents import (
            BaseAgent,
            AgentType,
            AgentResult,
            AgentRequest,
            RequestType,
            ExecutionPlan,
            AgentProgress,
            cache,
            SimpleCache,
            MainOrchestrator
        )
        print("✓ All imports successful")
        print(f"  - BaseAgent: {BaseAgent}")
        print(f"  - AgentType: {AgentType}")
        print(f"  - MainOrchestrator: {MainOrchestrator}")
        print(f"  - Cache instance: {cache}")
        return True
    except Exception as e:
        print(f"✗ Import failed: {e}")
        return False


async def test_cache_system():
    """Test 2: Verify cache functionality"""
    print("\n" + "="*60)
    print("TEST 2: Cache System")
    print("="*60)
    
    try:
        # Test set and get
        await cache.set("test_key", {"data": "test_value"})
        result = await cache.get("test_key")
        assert result == {"data": "test_value"}, "Cache get/set failed"
        print("✓ Cache set/get working")
        
        # Test fetch function
        async def fetch_data():
            return {"fetched": True}
        
        result = await cache.get("new_key", fetch_func=fetch_data, ttl_minutes=5)
        assert result == {"fetched": True}, "Cache fetch function failed"
        print("✓ Cache fetch function working")
        
        # Test stats
        stats = await cache.get_stats()
        print(f"✓ Cache stats: {stats['total_keys']} keys")
        
        # Test clear
        await cache.clear()
        stats = await cache.get_stats()
        assert stats['total_keys'] == 0, "Cache clear failed"
        print("✓ Cache clear working")
        
        return True
    except Exception as e:
        print(f"✗ Cache test failed: {e}")
        return False


async def test_orchestrator_basic():
    """Test 3: Basic orchestrator functionality"""
    print("\n" + "="*60)
    print("TEST 3: Orchestrator Basic Execution")
    print("="*60)
    
    try:
        orchestrator = MainOrchestrator()
        print(f"✓ Orchestrator created: {orchestrator.name}")
        print(f"  - Type: {orchestrator.agent_type}")
        print(f"  - Model: {orchestrator.model}")
        
        # Test basic execution
        request_data = {
            "type": "chat",
            "user_id": "test-user-123",
            "message": "Hello, this is a test",
            "options": {}
        }
        
        result = await orchestrator.execute(request_data)
        
        assert result.success, f"Execution failed: {result.error}"
        print(f"✓ Execution successful")
        print(f"  - Execution time: {result.execution_time_ms}ms")
        print(f"  - Intent: {result.data.get('intent')}")
        print(f"  - Phase: {result.data.get('phase')}")
        
        return True
    except Exception as e:
        print(f"✗ Orchestrator test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_intent_classification():
    """Test 4: Intent classification patterns"""
    print("\n" + "="*60)
    print("TEST 4: Intent Classification")
    print("="*60)
    
    test_cases = [
        ("Create flashcards about biology", "flashcard_generation"),
        ("Generate a quiz on chemistry", "quiz_generation"),
        ("Summarize my notes", "summary_generation"),
        ("Help me study for my exam", "exam_generation"),
        ("Analyze my notes on physics", "note_analysis"),
        ("Just chatting", "chat"),
    ]
    
    orchestrator = MainOrchestrator()
    passed = 0
    failed = 0
    
    for message, expected_intent in test_cases:
        try:
            request_data = {
                "type": "chat",
                "user_id": "test-user",
                "message": message,
                "options": {}
            }
            
            result = await orchestrator.execute(request_data)
            actual_intent = result.data.get('intent')
            
            if actual_intent == expected_intent:
                print(f"✓ '{message[:40]}...' -> {actual_intent}")
                passed += 1
            else:
                print(f"✗ '{message[:40]}...' -> Expected: {expected_intent}, Got: {actual_intent}")
                failed += 1
                
        except Exception as e:
            print(f"✗ Error testing '{message}': {e}")
            failed += 1
    
    print(f"\nResults: {passed} passed, {failed} failed")
    return failed == 0


async def test_progress_callbacks():
    """Test 5: Progress callback system"""
    print("\n" + "="*60)
    print("TEST 5: Progress Callbacks")
    print("="*60)
    
    try:
        orchestrator = MainOrchestrator()
        progress_updates = []
        
        async def progress_callback(progress):
            progress_updates.append(progress)
            print(f"  Progress: {progress.step}/{progress.total_steps} - {progress.message}")
        
        orchestrator.add_progress_callback(progress_callback)
        
        request_data = {
            "type": "flashcard_generation",
            "user_id": "test-user",
            "message": "Create flashcards",
            "options": {}
        }
        
        result = await orchestrator.execute(request_data)
        
        assert len(progress_updates) > 0, "No progress updates received"
        print(f"✓ Received {len(progress_updates)} progress updates")
        
        return True
    except Exception as e:
        print(f"✗ Progress callback test failed: {e}")
        return False


async def test_execution_plan():
    """Test 6: Execution plan generation"""
    print("\n" + "="*60)
    print("TEST 6: Execution Plan Generation")
    print("="*60)
    
    try:
        orchestrator = MainOrchestrator()
        
        request_data = {
            "type": "flashcard_generation",
            "user_id": "test-user",
            "message": "Create flashcards about Python",
            "options": {}
        }
        
        result = await orchestrator.execute(request_data)
        plan = result.data.get('execution_plan')
        
        assert plan is not None, "No execution plan generated"
        assert 'steps' in plan, "Plan missing steps"
        assert len(plan['steps']) > 0, "Plan has no steps"
        
        print(f"✓ Execution plan generated")
        print(f"  - Steps: {len(plan['steps'])}")
        print(f"  - Estimated time: {plan['estimated_time_ms']}ms")
        
        for i, step in enumerate(plan['steps'], 1):
            print(f"  {i}. {step['agent']}: {step['description']}")
        
        return True
    except Exception as e:
        print(f"✗ Execution plan test failed: {e}")
        return False


async def test_request_types():
    """Test 7: All request types"""
    print("\n" + "="*60)
    print("TEST 7: All Request Types")
    print("="*60)
    
    orchestrator = MainOrchestrator()
    request_types = [
        RequestType.CHAT,
        RequestType.FLASHCARD_GENERATION,
        RequestType.QUIZ_GENERATION,
        RequestType.EXAM_GENERATION,
        RequestType.SUMMARY_GENERATION,
        RequestType.NOTE_ANALYSIS,
        RequestType.STUDY_PLAN
    ]
    
    passed = 0
    failed = 0
    
    for req_type in request_types:
        try:
            request_data = {
                "type": req_type.value,
                "user_id": "test-user",
                "message": f"Test message for {req_type.value}",
                "options": {}
            }
            
            result = await orchestrator.execute(request_data)
            
            if result.success:
                print(f"✓ {req_type.value}")
                passed += 1
            else:
                print(f"✗ {req_type.value}: {result.error}")
                failed += 1
                
        except Exception as e:
            print(f"✗ {req_type.value}: {e}")
            failed += 1
    
    print(f"\nResults: {passed} passed, {failed} failed")
    return failed == 0


async def run_all_tests():
    """Run all tests"""
    print("\n" + "="*60)
    print("PHASE 1 AGENT SYSTEM TEST SUITE")
    print("="*60)
    
    tests = [
        ("Base Imports", test_base_imports),
        ("Cache System", test_cache_system),
        ("Orchestrator Basic", test_orchestrator_basic),
        ("Intent Classification", test_intent_classification),
        ("Progress Callbacks", test_progress_callbacks),
        ("Execution Plan", test_execution_plan),
        ("Request Types", test_request_types),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            result = await test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"\n✗ {test_name} crashed: {e}")
            results.append((test_name, False))
    
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
        print("\n🎉 All tests passed! Phase 1 agent system is ready.")
    else:
        print(f"\n⚠️  {failed} test(s) failed. Please review the errors above.")
    
    return failed == 0


if __name__ == "__main__":
    success = asyncio.run(run_all_tests())
    sys.exit(0 if success else 1)
