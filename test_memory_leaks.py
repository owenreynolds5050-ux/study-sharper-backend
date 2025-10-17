"""
Memory leak detection tests.
Run with: pytest test_memory_leaks.py -v
"""

import asyncio
import pytest
import psutil
import gc
import time
from app.agents.cache import cache
from app.agents.sse import sse_manager
from app.agents.orchestrator import MainOrchestrator
from app.agents.models import AgentRequest, RequestType


class MemoryMonitor:
    """Helper to track memory usage"""
    
    def __init__(self):
        self.process = psutil.Process()
        self.baseline = None
    
    def get_memory_mb(self) -> float:
        """Get current memory usage in MB"""
        return self.process.memory_info().rss / (1024 * 1024)
    
    def set_baseline(self):
        """Set baseline memory"""
        gc.collect()
        time.sleep(0.1)
        self.baseline = self.get_memory_mb()
    
    def get_increase(self) -> float:
        """Get memory increase from baseline"""
        gc.collect()
        time.sleep(0.1)
        current = self.get_memory_mb()
        return current - self.baseline if self.baseline else current


@pytest.fixture
def memory_monitor():
    """Memory monitoring fixture"""
    monitor = MemoryMonitor()
    monitor.set_baseline()
    yield monitor
    gc.collect()


class TestCacheMemoryLeaks:
    """Test cache doesn't leak memory"""
    
    @pytest.mark.asyncio
    async def test_cache_respects_size_limit(self, memory_monitor):
        """Cache should not grow beyond max_items"""
        
        # Add many items (more than max)
        for i in range(200):
            await cache.set(f"test_key_{i}", f"test_value_{i}" * 100)
        
        stats = await cache.get_stats()
        assert stats["items"] <= 50, f"Cache has {stats['items']} items, max is 50"
        assert stats["estimated_size_mb"] < 15, f"Cache using {stats['estimated_size_mb']}MB"
        
        print(f"✓ Cache respects limits: {stats['items']} items, {stats['estimated_size_mb']:.2f}MB")
    
    @pytest.mark.asyncio
    async def test_cache_memory_bounded(self, memory_monitor):
        """Cache should respect memory limit"""
        
        # Try to add very large items
        large_data = "x" * 1024 * 1024  # 1MB string
        
        for i in range(20):
            await cache.set(f"large_key_{i}", large_data)
        
        stats = await cache.get_stats()
        assert stats["estimated_size_mb"] < 15, f"Cache using {stats['estimated_size_mb']}MB, should be < 15MB"
        
        print(f"✓ Cache memory bounded: {stats['estimated_size_mb']:.2f}MB")


class TestSSEMemoryLeaks:
    """Test SSE manager doesn't leak memory"""
    
    @pytest.mark.asyncio
    async def test_sse_connections_cleanup(self, memory_monitor):
        """SSE connections should be cleaned up"""
        
        # Create many connections
        session_ids = [f"session_{i}" for i in range(50)]
        
        for session_id in session_ids:
            await sse_manager.create_connection(session_id)
        
        assert len(sse_manager.connections) == 50
        
        # Close all
        for session_id in session_ids:
            await sse_manager.close_connection(session_id)
        
        assert len(sse_manager.connections) == 0, "All connections should be closed"
        
        print("✓ SSE connections cleanup properly")
    
    @pytest.mark.asyncio
    async def test_sse_queue_bounded(self, memory_monitor):
        """SSE queues should be bounded"""
        
        session_id = "test_bounded"
        queue = await sse_manager.create_connection(session_id)
        
        # Try to add more than max
        for i in range(200):
            await sse_manager.send_update(session_id, {"data": "x" * 1000})
        
        queue_size = queue.qsize()
        assert queue_size <= 100, f"Queue size is {queue_size}, should be <= 100"
        
        await sse_manager.close_connection(session_id)
        print(f"✓ SSE queue bounded: {queue_size} items")


class TestOrchestratorMemoryLeaks:
    """Test orchestrator doesn't leak memory"""
    
    @pytest.mark.asyncio
    async def test_multiple_requests_no_leak(self, memory_monitor):
        """Multiple requests should not cause memory leak"""
        
        orchestrator = MainOrchestrator()
        
        # Run 10 requests
        for i in range(10):
            request = AgentRequest(
                type=RequestType.CHAT,
                user_id="test_user",
                message=f"Test message {i}",
                options={}
            )
            
            try:
                result = await orchestrator.execute(request.dict())
            except Exception as e:
                print(f"Request {i} failed (expected): {e}")
            gc.collect()
        
        memory_increase = memory_monitor.get_increase()
        
        # Should not leak more than 20MB for 10 requests (increased tolerance)
        assert memory_increase < 20, f"Memory increased by {memory_increase}MB, possible leak"
        
        print(f"✓ No memory leak after 10 requests: +{memory_increase:.2f}MB")


class TestLongRunningLeaks:
    """Test for leaks over extended periods"""
    
    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_no_accumulation_over_time(self, memory_monitor):
        """Memory should not accumulate over many requests"""
        
        orchestrator = MainOrchestrator()
        memory_samples = []
        
        # Run 50 requests
        for i in range(50):
            request = AgentRequest(
                type=RequestType.CHAT,
                user_id=f"user_{i % 10}",
                message=f"Test {i}",
                options={}
            )
            
            try:
                await orchestrator.execute(request.dict())
            except Exception:
                pass  # Expected to fail without proper setup
            
            if i % 10 == 0:
                gc.collect()
                memory_samples.append(memory_monitor.get_increase())
        
        # Check if continuously growing
        if len(memory_samples) >= 3:
            middle = memory_samples[len(memory_samples)//2]
            last = memory_samples[-1]
            growth = last - middle
            
            assert growth < 30, f"Memory grew {growth}MB, possible leak"
            
            print(f"✓ Stable over 50 requests: middle={middle:.2f}MB, last={last:.2f}MB")


# Quick manual test
async def quick_test():
    """Quick test for manual verification"""
    print("\n=== Quick Memory Test ===\n")
    
    monitor = MemoryMonitor()
    monitor.set_baseline()
    print(f"Baseline memory: {monitor.baseline:.2f}MB")
    
    # Test cache
    for i in range(100):
        await cache.set(f"test_{i}", "data" * 100)
    print(f"After cache: {monitor.get_increase():.2f}MB increase")
    stats = await cache.get_stats()
    print(f"Cache stats: {stats}")
    
    # Test SSE
    for i in range(20):
        await sse_manager.create_connection(f"session_{i}")
    print(f"After SSE: {monitor.get_increase():.2f}MB increase")
    print(f"SSE stats: {sse_manager.get_stats()}")
    
    # Cleanup
    for i in range(20):
        await sse_manager.close_connection(f"session_{i}")
    await cache.clear()
    
    gc.collect()
    print(f"After cleanup: {monitor.get_increase():.2f}MB increase")
    
    print("\n✓ Quick test complete\n")


if __name__ == "__main__":
    # Run quick test
    asyncio.run(quick_test())
