"""
Redis Cache Module
Provides caching for geocoding and distance matrix results
"""

import json
import logging
from typing import Optional
from config import REDIS_URL, REDIS_ENABLED, REDIS_CACHE_TTL

logger = logging.getLogger(__name__)

# Redis client (lazy initialization)
_redis_client = None


def get_redis_client():
    """ดึง Redis client (lazy initialization)"""
    global _redis_client
    
    if not REDIS_ENABLED:
        return None
    
    if _redis_client is not None:
        return _redis_client
    
    try:
        import redis
        _redis_client = redis.from_url(REDIS_URL, decode_responses=True)
        # ทดสอบการเชื่อมต่อ
        _redis_client.ping()
        logger.info(f"Redis connected: {REDIS_URL}")
        return _redis_client
    except Exception as e:
        logger.warning(f"Redis connection failed: {e} - falling back to in-memory cache")
        _redis_client = None
        return None


def get_cached(key: str) -> Optional[dict]:
    """ดึงข้อมูลจาก Redis cache"""
    client = get_redis_client()
    if client is None:
        return None
    
    try:
        data = client.get(key)
        if data:
            return json.loads(data)
        return None
    except Exception as e:
        logger.warning(f"Redis get error: {e}")
        return None


def set_cached(key: str, value: dict, ttl: int = None):
    """บันทึกข้อมูลลง Redis cache"""
    client = get_redis_client()
    if client is None:
        return
    
    try:
        if ttl is None:
            ttl = REDIS_CACHE_TTL
        
        data = json.dumps(value, ensure_ascii=False)
        client.setex(key, ttl, data)
    except Exception as e:
        logger.warning(f"Redis set error: {e}")


def delete_cached(key: str):
    """ลบข้อมูลจาก Redis cache"""
    client = get_redis_client()
    if client is None:
        return
    
    try:
        client.delete(key)
    except Exception as e:
        logger.warning(f"Redis delete error: {e}")


def clear_cache():
    """ล้าง cache keys ที่ขึ้นต้นด้วย prefix (ไม่ลบข้อมูลอื่น เช่น task status)"""
    client = get_redis_client()
    if client is None:
        return

    try:
        deleted = 0
        # Scan all known prefixes: dm: (distance matrix), geo: (geocoding), cache: (generic)
        for prefix in ("dm:*", "geo:*", "cache:*"):
            cursor = 0
            while True:
                cursor, keys = client.scan(cursor, match=prefix, count=100)
                if keys:
                    client.delete(*keys)
                    deleted += len(keys)
                if cursor == 0:
                    break
        logger.info(f"Cache cleared: {deleted} keys deleted")
    except Exception as e:
        logger.warning(f"Redis clear error: {e}")


def get_cache_stats() -> dict:
    """ดึงสถิติ Redis cache"""
    client = get_redis_client()
    if client is None:
        return {"status": "disabled", "connected": False}
    
    try:
        info = client.info()
        return {
            "status": "enabled",
            "connected": True,
            "keys": info.get("db0", {}).get("keys", 0),
            "memory_used": info.get("used_memory_human", "N/A"),
            "uptime_seconds": info.get("uptime_in_seconds", 0)
        }
    except Exception as e:
        return {"status": "error", "connected": False, "error": str(e)}
