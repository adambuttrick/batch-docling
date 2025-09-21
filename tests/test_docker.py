import os
import redis
import tempfile
from pathlib import Path
from docling_service.config import get_config

def test_redis_connection():
    try:
        config = get_config()
        redis_url = config.get_redis_url()
        r = redis.Redis.from_url(redis_url)
        r.ping()
        print(f"✓ Redis connection successful: {redis_url}")
        return True
    except Exception as e:
        print(f"✗ Redis connection failed: {e}")
        return False

def test_directories():
    try:
        config = get_config()
        output_dir = config.get_default_output_dir()
        watch_dir = config.get("daemon", "watch_directory")
        
        print(f"✓ Output directory: {output_dir}")
        print(f"✓ Watch directory: {watch_dir}")
        
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        Path(watch_dir).mkdir(parents=True, exist_ok=True)
        
        return True
    except Exception as e:
        print(f"✗ Directory test failed: {e}")
        return False

def test_celery_import():
    try:
        from docling_service.celery_app import celery_app
        print(f"✓ Celery app imported successfully")
        print(f"✓ Broker: {celery_app.broker}")
        return True
    except Exception as e:
        print(f"✗ Celery import failed: {e}")
        return False

def main():
    print("Docker Environment Test")
    print("=" * 30)
    
    tests = [
        test_redis_connection,
        test_directories, 
        test_celery_import
    ]
    
    passed = 0
    for test in tests:
        if test():
            passed += 1
        print()
    
    print(f"Results: {passed}/{len(tests)} tests passed")
    
    if passed == len(tests):
        print("✓ All tests passed - Docker environment ready")
        return 0
    else:
        print("✗ Some tests failed - Check configuration")
        return 1

if __name__ == "__main__":
    exit(main())