"""
Simple In-Memory Cache System
Provides TTL-based caching for agent results and frequently accessed data
"""

from datetime import datetime, timedelta
from typing import Any, Optional, Callable
import asyncio
import logging

logger = logging.getLogger(__name__)


class SimpleCache:
    """
    Simple in-memory cache with TTL (Time To Live).
    Thread-safe using asyncio locks.
    """
    
    def __init__(self):
        self._cache: dict = {}
        self._lock = asyncio.Lock()
        logger.info("SimpleCache initialized")
    
    async def get(
        self,
        key: str,
        fetch_func: Optional[Callable] = None,
        ttl_minutes: int = 10
    ) -> Optional[Any]:
        """
        Get value from cache or fetch if missing.
        
        Args:
            key: Cache key
            fetch_func: Optional function to fetch data if cache miss
            ttl_minutes: Time to live in minutes
            
        Returns:
            Cached value or fetched value, None if not found
        """
        async with self._lock:
            if key in self._cache:
                data, timestamp = self._cache[key]
                age = datetime.now() - timestamp
                
                if age < timedelta(minutes=ttl_minutes):
                    logger.debug(f"Cache HIT: {key} (age: {age.total_seconds():.1f}s)")
                    return data
                else:
                    # Expired
                    logger.debug(f"Cache EXPIRED: {key} (age: {age.total_seconds():.1f}s)")
                    del self._cache[key]
            
            # Cache miss
            logger.debug(f"Cache MISS: {key}")
            
            if fetch_func:
                try:
                    if asyncio.iscoroutinefunction(fetch_func):
                        data = await fetch_func()
                    else:
                        data = fetch_func()
                    
                    self._cache[key] = (data, datetime.now())
                    logger.debug(f"Cache SET: {key}")
                    return data
                except Exception as e:
                    logger.error(f"Error fetching data for cache key {key}: {e}")
                    return None
            
            return None
    
    async def set(self, key: str, value: Any):
        """
        Manually set cache value.
        
        Args:
            key: Cache key
            value: Value to cache
        """
        async with self._lock:
            self._cache[key] = (value, datetime.now())
            logger.debug(f"Cache SET: {key}")
    
    async def delete(self, key: str) -> bool:
        """
        Delete a specific cache entry.
        
        Args:
            key: Cache key to delete
            
        Returns:
            True if key existed and was deleted, False otherwise
        """
        async with self._lock:
            if key in self._cache:
                del self._cache[key]
                logger.debug(f"Cache DELETE: {key}")
                return True
            return False
    
    async def clear(self, pattern: Optional[str] = None):
        """
        Clear cache entries.
        
        Args:
            pattern: Optional pattern to match keys (substring match)
                    If None, clears entire cache
        """
        async with self._lock:
            if pattern:
                keys_to_delete = [k for k in self._cache.keys() if pattern in k]
                for key in keys_to_delete:
                    del self._cache[key]
                logger.info(f"Cache CLEAR: {len(keys_to_delete)} keys matching '{pattern}'")
            else:
                count = len(self._cache)
                self._cache.clear()
                logger.info(f"Cache CLEAR: All {count} keys")
    
    async def get_stats(self) -> dict:
        """
        Get cache statistics.
        
        Returns:
            Dictionary with cache stats
        """
        async with self._lock:
            total_keys = len(self._cache)
            
            if total_keys == 0:
                return {
                    "total_keys": 0,
                    "oldest_entry_age_seconds": 0,
                    "newest_entry_age_seconds": 0,
                    "average_age_seconds": 0
                }
            
            now = datetime.now()
            ages = [(now - timestamp).total_seconds() for _, timestamp in self._cache.values()]
            
            return {
                "total_keys": total_keys,
                "oldest_entry_age_seconds": max(ages),
                "newest_entry_age_seconds": min(ages),
                "average_age_seconds": sum(ages) / len(ages)
            }
    
    def get_size(self) -> int:
        """
        Get current cache size (number of keys).
        Non-async for quick checks.
        
        Returns:
            Number of cached keys
        """
        return len(self._cache)


# Global cache instance
cache = SimpleCache()
