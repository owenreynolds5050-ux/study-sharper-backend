import asyncio
from app.agents.cache import cache

async def test_cache():
    print("Testing cache bounds...")
    
    # Add 100 items (should only keep 50)
    for i in range(100):
        await cache.set(f"key_{i}", "data" * 1000)
    
    stats = await cache.get_stats()
    print(f"\n✅ Cache Stats:")
    print(f"   Items: {stats['items']} (should be ≤ 50)")
    print(f"   Max Items: {stats['max_items']}")
    print(f"   Memory: {stats['estimated_size_mb']:.2f}MB (should be < 10MB)")
    print(f"   Max Memory: {stats['max_size_mb']}MB")
    
    assert stats['items'] <= 50, "Cache exceeded max items!"
    assert stats['estimated_size_mb'] < 10, "Cache exceeded max memory!"
    print("\n✅ Cache bounds working correctly!")

if __name__ == "__main__":
    asyncio.run(test_cache())