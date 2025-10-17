"""
Simple load test to verify memory doesn't explode under concurrent requests.
Usage: python load_test.py
"""

import asyncio
import aiohttp
import time
import sys

async def make_request(session, i, base_url):
    """Make single request"""
    try:
        async with session.post(
            f"{base_url}/api/ai/agent-test",
            json={
                "type": "chat",
                "user_id": f"test_user_{i % 5}",
                "message": f"Test message {i}",
                "options": {}
            },
            timeout=aiohttp.ClientTimeout(total=30)
        ) as response:
            status = response.status
            if status == 200:
                return True
            else:
                print(f"Request {i} returned status {status}")
                return False
    except asyncio.TimeoutError:
        print(f"Request {i} timed out")
        return False
    except Exception as e:
        print(f"Request {i} failed: {e}")
        return False

async def check_health(base_url):
    """Check if server is healthy"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{base_url}/health",
                timeout=aiohttp.ClientTimeout(total=5)
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"✓ Server healthy: {data.get('status')}")
                    return True
                else:
                    print(f"✗ Server returned status {response.status}")
                    return False
    except Exception as e:
        print(f"✗ Health check failed: {e}")
        return False

async def load_test(concurrent=10, total=50, base_url="http://localhost:8000"):
    """Run load test"""
    print(f"\n=== Load Test ===")
    print(f"Target: {base_url}")
    print(f"Total requests: {total}")
    print(f"Concurrent: {concurrent}")
    print("=" * 50)
    
    # Check health first
    print("\nChecking server health...")
    if not await check_health(base_url):
        print("\n✗ Server not healthy. Start the server first:")
        print("  uvicorn app.main:app --reload")
        return
    
    print("\nStarting load test...\n")
    start = time.time()
    success_count = 0
    
    async with aiohttp.ClientSession() as session:
        # Run in batches
        for batch_start in range(0, total, concurrent):
            batch_size = min(concurrent, total - batch_start)
            tasks = [
                make_request(session, batch_start + i, base_url)
                for i in range(batch_size)
            ]
            
            results = await asyncio.gather(*tasks)
            success_count += sum(results)
            
            completed = batch_start + batch_size
            print(f"Progress: {completed}/{total} requests ({success_count} successful)")
    
    duration = time.time() - start
    
    print(f"\n{'=' * 50}")
    print("=== Results ===")
    print(f"{'=' * 50}")
    print(f"Total requests: {total}")
    print(f"Successful: {success_count} ({success_count/total*100:.1f}%)")
    print(f"Failed: {total - success_count}")
    print(f"Duration: {duration:.2f}s")
    print(f"Requests/second: {total/duration:.2f}")
    
    if success_count / total >= 0.9:
        print("\n✅ Load test PASSED (>90% success rate)")
    else:
        print("\n⚠️  Load test WARNING (low success rate)")
    
    print(f"\nCheck memory usage:")
    print(f"  curl {base_url}/api/admin/metrics")
    print()

if __name__ == "__main__":
    # Parse command line arguments
    base_url = "http://localhost:8000"
    if len(sys.argv) > 1:
        base_url = sys.argv[1]
    
    print(f"\nLoad Testing: {base_url}")
    print("Press Ctrl+C to cancel\n")
    
    try:
        asyncio.run(load_test(concurrent=10, total=50, base_url=base_url))
    except KeyboardInterrupt:
        print("\n\nLoad test cancelled by user")
