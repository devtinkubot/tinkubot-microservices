#!/usr/bin/env python3
"""
Example usage of the Service Profession Mapping Admin API.

This script demonstrates how to use the cache invalidation endpoints.

To run the service:
    cd python-services/ai-clientes
    python3 main.py

Then use curl or any HTTP client to interact with the API.

Examples:
    # Get cache statistics
    curl http://localhost:8001/admin/service-mapping/cache/stats

    # Refresh cache for a specific service
    curl -X POST http://localhost:8001/admin/service-mapping/cache/refresh/inyección

    # Refresh all cache
    curl -X POST http://localhost:8001/admin/service-mapping/cache/refresh

    # Get mapping for a service
    curl http://localhost:8001/admin/service-mapping/service/suero

    # Health check
    curl http://localhost:8001/admin/service-mapping/health
"""

import requests
from typing import Dict, Any
import json


BASE_URL = "http://localhost:8001/admin/service-mapping"


def print_response(title: str, response: requests.Response) -> None:
    """Pretty print API response."""
    print(f"\n{'='*60}")
    print(f"{title}")
    print(f"{'='*60}")
    print(f"Status Code: {response.status_code}")
    print(f"Response:")
    try:
        print(json.dumps(response.json(), indent=2))
    except Exception:
        print(response.text)


def example_get_cache_stats() -> None:
    """Example: Get cache statistics."""
    response = requests.get(f"{BASE_URL}/cache/stats")
    print_response("Cache Statistics", response)


def example_refresh_service_cache(service_name: str) -> None:
    """Example: Refresh cache for a specific service."""
    response = requests.post(f"{BASE_URL}/cache/refresh/{service_name}")
    print_response(f"Refresh Cache for '{service_name}'", response)


def example_refresh_all_cache() -> None:
    """Example: Refresh all cache."""
    response = requests.post(f"{BASE_URL}/cache/refresh")
    print_response("Refresh All Cache", response)


def example_get_service_mapping(service_name: str) -> None:
    """Example: Get service-profession mapping."""
    response = requests.get(f"{BASE_URL}/service/{service_name}")
    print_response(f"Service Mapping for '{service_name}'", response)


def example_health_check() -> None:
    """Example: Health check."""
    response = requests.get(f"{BASE_URL}/health")
    print_response("Health Check", response)


if __name__ == "__main__":
    import sys

    print("=" * 60)
    print("Service Profession Mapping Admin API - Examples")
    print("=" * 60)

    # Check if service is running
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=2)
        if response.status_code != 200:
            print("❌ Service is not healthy")
            sys.exit(1)
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to service. Is it running?")
        print("Start the service with: cd python-services/ai-clientes && python3 main.py")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

    # Run examples
    print("\n🔍 Running examples...\n")

    # 1. Health check
    example_health_check()

    # 2. Get cache stats
    example_get_cache_stats()

    # 3. Get mapping for a service
    example_get_service_mapping("inyección")

    # 4. Refresh cache for a specific service
    example_refresh_service_cache("inyección")

    # 5. Refresh all cache (commented out to avoid bulk invalidation)
    # print("\n⚠️ Skipping bulk cache refresh (uncomment to test)")
    # example_refresh_all_cache()

    print("\n" + "=" * 60)
    print("✅ Examples completed!")
    print("=" * 60)
