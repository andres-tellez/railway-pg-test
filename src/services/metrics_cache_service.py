"""
Metrics Cache Service
=====================

Provides caching layer for metrics data to improve performance.
Uses in-memory caching with TTL for simplicity.

Features:
- 5-minute cache TTL for metrics data
- Cache invalidation on data updates
- Fallback to database on cache miss
- Performance monitoring
"""

import time
import hashlib
from typing import Dict, Optional, Any
from functools import wraps
from datetime import datetime, timedelta
import json

# Simple in-memory cache (can be replaced with Redis later)
_metrics_cache: Dict[str, Dict[str, Any]] = {}
CACHE_TTL_SECONDS = 300  # 5 minutes

def _get_cache_key(athlete_id: int, cache_type: str, **kwargs) -> str:
    """Generate a unique cache key for the given parameters."""
    key_data = {
        'athlete_id': athlete_id,
        'cache_type': cache_type,
        **kwargs
    }
    key_str = json.dumps(key_data, sort_keys=True)
    return hashlib.md5(key_str.encode()).hexdigest()

def _is_cache_valid(cache_entry: Dict[str, Any]) -> bool:
    """Check if cache entry is still valid based on TTL."""
    if not cache_entry:
        return False
    
    created_at = cache_entry.get('created_at', 0)
    ttl = cache_entry.get('ttl', CACHE_TTL_SECONDS)
    return time.time() - created_at < ttl

def get_cached_metrics(cache_key: str) -> Optional[Any]:
    """Retrieve metrics from cache if valid."""
    cache_entry = _metrics_cache.get(cache_key)
    
    if cache_entry and _is_cache_valid(cache_entry):
        return cache_entry['data']
    
    # Remove expired entry
    if cache_entry:
        del _metrics_cache[cache_key]
    
    return None

def set_cached_metrics(cache_key: str, data: Any, ttl: int = CACHE_TTL_SECONDS) -> None:
    """Store metrics in cache with TTL."""
    _metrics_cache[cache_key] = {
        'data': data,
        'created_at': time.time(),
        'ttl': ttl
    }

def invalidate_athlete_cache(athlete_id: int) -> None:
    """Invalidate all cache entries for a specific athlete."""
    keys_to_remove = []
    for key in _metrics_cache.keys():
        if f'athlete_id": {athlete_id}' in key:
            keys_to_remove.append(key)
    
    for key in keys_to_remove:
        del _metrics_cache[key]

def cache_metrics(cache_type: str, ttl: int = CACHE_TTL_SECONDS):
    """Decorator to cache metrics function results."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Extract athlete_id from arguments
            athlete_id = None
            if args:
                athlete_id = args[0] if isinstance(args[0], int) else None
            elif 'athlete_id' in kwargs:
                athlete_id = kwargs['athlete_id']
            
            if not athlete_id:
                return func(*args, **kwargs)
            
            # Generate cache key
            cache_key = _get_cache_key(athlete_id, cache_type, **kwargs)
            
            # Try to get from cache
            cached_result = get_cached_metrics(cache_key)
            if cached_result is not None:
                print(f"[CACHE HIT] {cache_type} for athlete {athlete_id}")
                return cached_result
            
            # Cache miss - execute function and cache result
            print(f"[CACHE MISS] {cache_type} for athlete {athlete_id}")
            result = func(*args, **kwargs)
            
            if result is not None:
                set_cached_metrics(cache_key, result, ttl)
            
            return result
        
        return wrapper
    return decorator

def get_cache_stats() -> Dict[str, Any]:
    """Get cache statistics for monitoring."""
    total_entries = len(_metrics_cache)
    valid_entries = sum(1 for entry in _metrics_cache.values() if _is_cache_valid(entry))
    expired_entries = total_entries - valid_entries
    
    return {
        'total_entries': total_entries,
        'valid_entries': valid_entries,
        'expired_entries': expired_entries,
        'cache_hit_ratio': 'N/A',  # Would need hit/miss counters
        'memory_usage_mb': sum(len(str(entry)) for entry in _metrics_cache.values()) / 1024 / 1024
    }

def clear_cache() -> None:
    """Clear all cache entries."""
    _metrics_cache.clear()
    print("[CACHE] All cache entries cleared")
