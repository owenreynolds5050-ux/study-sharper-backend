from app.agents.sse import sse_manager

def test_sse():
    print("Testing SSE manager...")
    stats = sse_manager.get_stats()
    print(f"\n✅ SSE Stats:")
    print(f"   Active Connections: {stats['active_connections']}")
    print(f"   Oldest Connection Age: {stats['oldest_connection_age_seconds']}s")
    print("\n✅ SSE manager initialized correctly!")

if __name__ == "__main__":
    test_sse()
