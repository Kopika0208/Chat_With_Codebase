from upstash_redis import Redis
import json
import os
from typing import Any, Optional, List

redis = Redis(
    url=os.getenv("UPSTASH_REDIS_REST_URL"),
    token=os.getenv("UPSTASH_REDIS_REST_TOKEN")
)


def save_json(repo_name: str, data_type: str, data: Any) -> str:
    """Save JSON data to Redis with key pattern repo:{repo_name}:{data_type}"""
    key = f"repo:{repo_name}:{data_type}"
    redis.set(key, json.dumps(data, default=str))
    return key


def get_json(repo_name: str, data_type: str) -> Optional[dict]:
    """Retrieve JSON data from Redis"""
    key = f"repo:{repo_name}:{data_type}"
    data = redis.get(key)
    if data is None:
        return None
    if isinstance(data, bytes):
        data = data.decode("utf-8")
    return json.loads(data)


def list_repos() -> List[str]:
    """List all stored repositories"""
    keys = redis.keys("repo:*") or []
    repos = set()
    for k in keys:
        if isinstance(k, bytes):
            k = k.decode("utf-8")
        parts = k.split(":")
        if len(parts) >= 3:
            repos.add(parts[1])
    return sorted(repos)


def save_json_key(key: str, data: Any) -> str:
    """Save JSON data to Redis using an explicit Redis key."""
    redis.set(key, json.dumps(data, default=str))
    return key


def get_json_by_key(key: str) -> Optional[Any]:
    """Retrieve JSON data from Redis by an explicit key."""
    data = redis.get(key)
    if data is None:
        return None
    if isinstance(data, bytes):
        data = data.decode("utf-8")
    return json.loads(data)


def list_keys(pattern: str) -> List[str]:
    """List Redis keys matching a pattern."""
    keys = redis.keys(pattern) or []
    normalized_keys = []
    for k in keys:
        if isinstance(k, bytes):
            k = k.decode("utf-8")
        normalized_keys.append(k)
    return normalized_keys


def delete_keys(pattern: str) -> int:
    """Delete Redis keys matching a pattern."""
    keys = list_keys(pattern)
    return redis.delete(*keys) if keys else 0


def delete_repo(repo_name: str) -> int:
    """Delete all data for a repository"""
    return delete_keys(f"repo:{repo_name}:*")


def repo_exists(repo_name: str, data_type: str) -> bool:
    """Check if data exists for repo"""
    return redis.exists(f"repo:{repo_name}:{data_type}") > 0
