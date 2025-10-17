"""
Simple In-Memory Cache System
Provides TTL-based caching for agent results and frequently accessed data
"""

from datetime import datetime, timedelta
from typing import Any, Optional, Callable
from collections import OrderedDict
import asyncio
import logging
import sys

logger = logging.getLogger(__name__)


class SimpleCache:
    """
    Bounded in-memory cache with TTL (Time To Live) and LRU eviction.
    Thread-safe using asyncio locks.
    Limits: max_items and max_memory_mb to prevent unbounded growth.
    """
    
    def __init__(self, max_items: int = 50, max_memory_mb: float = 10.0):
        self._cache: OrderedDict = OrderedDict()  # LRU ordering
        self._lock = asyncio.Lock()
        self.max_items = max_items
        self.max_memory_mb = max_memory_mb
        self._total_size_bytes = 0
        logger.info(f"SimpleCache initialized (max_items={max_items}, max_memory_mb={max_memory_mb}MB)")
    
    def _estimate_size(self, value: Any) -> int:
        """Rough memory size estimate in bytes"""
        if isinstance(value, (str, bytes)):
            return sys.getsizeof(value)
        elif isinstance(value, dict):
            return sum(sys.getsizeof(k) + self._estimate_size(v) for k, v in value.items())
        elif isinstance(value, list):
            return sum(self._estimate_size(item) for item in value)
        else:
            return sys.getsizeof(value)
    
    def _evict_oldest(self):
        """Evict oldest item from cache (LRU)"""
        if self._cache:
            oldest_key, (_, _, size) = self._cache.popitem(last=False)
            self._total_size_bytes -= size
            logger.debug(f"Cache EVICT: {oldest_key} (freed {size} bytes)")
    
    def _enforce_limits(self, new_item_size: int):
        """Evict items until limits are satisfied"""
        # Evict by count limit
        while len(self._cache) >= self.max_items:
            self._evict_oldest()
        
        # Evict by memory limit
        max_bytes = self.max_memory_mb * 1024 * 1024
        while self._total_size_bytes + new_item_size > max_bytes and self._cache:
            self._evict_oldest()
    
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
                data, timestamp, size = self._cache[key]
                age = datetime.now() - timestamp
                
                if age < timedelta(minutes=ttl_minutes):
                    # Move to end (most recently used)
                    self._cache.move_to_end(key)
                    logger.debug(f"Cache HIT: {key} (age: {age.total_seconds():.1f}s)")
                    return data
                else:
                    # Expired
                    logger.debug(f"Cache EXPIRED: {key} (age: {age.total_seconds():.1f}s)")
                    del self._cache[key]
                    self._total_size_bytes -= size
            
            # Cache miss
            logger.debug(f"Cache MISS: {key}")
            
            if fetch_func:
                try:
                    if asyncio.iscoroutinefunction(fetch_func):
                        data = await fetch_func()
                    else:
                        data = fetch_func()
                    
                    # Estimate size and check if too large
                    item_size = self._estimate_size(data)
                    max_item_size = (self.max_memory_mb * 1024 * 1024) * 0.5
                    
                    if item_size > max_item_size:
                        logger.warning(f"Cache SKIP: {key} too large ({item_size} bytes > 50% limit)")
                        return data
                    
                    # Enforce limits before adding
                    self._enforce_limits(item_size)
                    
                    self._cache[key] = (data, datetime.now(), item_size)
                    self._total_size_bytes += item_size
                    logger.debug(f"Cache SET: {key} ({item_size} bytes)")
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
            # Estimate size
            item_size = self._estimate_size(value)
            max_item_size = (self.max_memory_mb * 1024 * 1024) * 0.5
            
            if item_size > max_item_size:
                logger.warning(f"Cache SKIP: {key} too large ({item_size} bytes > 50% limit)")
                return
            
            # Remove old entry if exists
            if key in self._cache:
                _, _, old_size = self._cache[key]
                self._total_size_bytes -= old_size
                del self._cache[key]
            
            # Enforce limits before adding
            self._enforce_limits(item_size)
            
            self._cache[key] = (value, datetime.now(), item_size)
            self._total_size_bytes += item_size
            logger.debug(f"Cache SET: {key} ({item_size} bytes)")
    
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
                _, _, size = self._cache[key]
                del self._cache[key]
                self._total_size_bytes -= size
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
                    _, _, size = self._cache[key]
                    self._total_size_bytes -= size
                    del self._cache[key]
                logger.info(f"Cache CLEAR: {len(keys_to_delete)} keys matching '{pattern}'")
            else:
                count = len(self._cache)
                self._cache.clear()
                self._total_size_bytes = 0
                logger.info(f"Cache CLEAR: All {count} keys")
    
    async def get_stats(self) -> dict:
        """
        Get cache statistics.
        
        Returns:
            Dictionary with cache stats including memory usage
        """
        async with self._lock:
            total_keys = len(self._cache)
            
            if total_keys == 0:
                return {
                    "items": 0,
                    "max_items": self.max_items,
                    "estimated_size_mb": 0.0,
                    "max_size_mb": self.max_memory_mb,
                    "oldest_entry_age_seconds": 0,
                    "newest_entry_age_seconds": 0,
                    "average_age_seconds": 0
                }
            
            now = datetime.now()
            ages = [(now - timestamp).total_seconds() for _, timestamp, _ in self._cache.values()]
            
            return {
                "items": total_keys,
                "max_items": self.max_items,
                "estimated_size_mb": self._total_size_bytes / (1024 * 1024),
                "max_size_mb": self.max_memory_mb,
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
