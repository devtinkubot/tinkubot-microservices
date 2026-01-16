# Service Profession Mapping Admin API

REST API endpoints for cache management of the ServiceProfessionMapper system.

## Overview

This API provides administrative endpoints for managing the service-profession mapping cache, allowing immediate weight updates without waiting for cache expiration (1 hour TTL).

## Features

- ✅ Manual cache invalidation (global or per-service)
- ✅ Cache statistics monitoring
- ✅ Health checks for the mapping system
- ✅ View current mappings
- ✅ Production-ready with proper error handling
- ✅ Pydantic models for request/response validation
- ✅ Type hints for Pyright validation

## Endpoints

### 1. Health Check

**GET** `/admin/service-mapping/health`

Check the health of the service-profession mapping system.

**Response:**
```json
{
  "status": "healthy",
  "service": "service-profession-mapping",
  "database": {
    "table_exists": true,
    "table_name": "service_profession_mapping"
  },
  "cache": {
    "enabled": true,
    "cached_services": 25
  },
  "timestamp": "2026-01-16T12:00:00.000Z"
}
```

### 2. Cache Statistics

**GET** `/admin/service-mapping/cache/stats`

Get detailed statistics about the service-profession mapping cache.

**Response:**
```json
{
  "service": "ai-clientes",
  "cache_type": "service_profession_mapping",
  "stats": {
    "enabled": true,
    "total_cached_services": 25,
    "cache_keys": ["service_mapping:inyección", "service_mapping:suero", ...],
    "cache_keys_truncated": false,
    "redis_memory_human": "256M",
    "redis_memory_bytes": 268435456,
    "key_details": [
      {
        "service": "inyección",
        "key": "service_mapping:inyección",
        "ttl_seconds": 3200
      }
    ]
  },
  "timestamp": "2026-01-16T12:00:00.000Z"
}
```

### 3. Refresh All Cache

**POST** `/admin/service-mapping/cache/refresh`

Invalidate ALL cached service-profession mappings.

**Warning:** This will cause a temporary increase in database load as mappings are re-fetched from PostgreSQL.

**Response:**
```json
{
  "success": true,
  "message": "Successfully invalidated 25 cache entries",
  "service_name": null,
  "invalidated_keys": [
    "service_mapping:inyección",
    "service_mapping:suero",
    ...
  ],
  "timestamp": "2026-01-16T12:00:00.000Z"
}
```

### 4. Refresh Service Cache

**POST** `/admin/service-mapping/cache/refresh/{service_name}`

Invalidate cache for a specific service only.

**Parameters:**
- `service_name` (path parameter): Name of the service (e.g., "inyección", "suero")

**Response:**
```json
{
  "success": true,
  "message": "Successfully invalidated cache for service 'inyección'",
  "service_name": "inyección",
  "invalidated_keys": ["service_mapping:inyección"],
  "timestamp": "2026-01-16T12:00:00.000Z"
}
```

### 5. Get Service Mapping

**GET** `/admin/service-mapping/service/{service_name}`

Retrieve the current service-profession mapping for a specific service.

**Parameters:**
- `service_name` (path parameter): Name of the service to look up

**Response:**
```json
{
  "service_name": "inyección",
  "primary_profession": "enfermero",
  "profession_count": 2,
  "professions": [
    {
      "profession": "enfermero",
      "score": 0.95,
      "is_primary": true
    },
    {
      "profession": "médico",
      "score": 0.70,
      "is_primary": false
    }
  ],
  "cached": true
}
```

## Usage Examples

### Using curl

```bash
# Health check
curl http://localhost:8001/admin/service-mapping/health

# Get cache statistics
curl http://localhost:8001/admin/service-mapping/cache/stats

# Refresh cache for a specific service
curl -X POST http://localhost:8001/admin/service-mapping/cache/refresh/inyección

# Refresh all cache
curl -X POST http://localhost:8001/admin/service-mapping/cache/refresh

# Get mapping for a service
curl http://localhost:8001/admin/service-mapping/service/suero
```

### Using Python

```python
import requests

BASE_URL = "http://localhost:8001/admin/service-mapping"

# Get cache stats
response = requests.get(f"{BASE_URL}/cache/stats")
stats = response.json()
print(f"Cached services: {stats['stats']['total_cached_services']}")

# Refresh specific service cache
response = requests.post(f"{BASE_URL}/cache/refresh/inyección")
result = response.json()
print(f"Success: {result['success']}, Message: {result['message']}")

# Get service mapping
response = requests.get(f"{BASE_URL}/service/inyección")
mapping = response.json()
print(f"Primary profession: {mapping['primary_profession']}")
```

### Using the example script

```bash
cd python-services/ai-clientes
python3 api/example_usage.py
```

## Integration

The API is automatically registered when the ai-clientes service starts:

1. The `ServiceProfessionMapper` is initialized during startup
2. The mapper instance is registered with the admin API
3. The router is included in the FastAPI application
4. Endpoints are available at `/admin/service-mapping/*`

## Architecture

### SOLID Principles

- **Single Responsibility Principle (SRP):** Each endpoint has a single, well-defined purpose
- **Open/Closed Principle (OCP):** The API is open to extension (new endpoints can be added) but closed for modification
- **Dependency Inversion Principle (DIP):** Depends on abstractions (ServiceProfessionMapper protocol)

### Cache Invalidation Strategy

The API uses Redis SCAN for safe cache key enumeration:

- **Pattern-based matching:** Uses `service_mapping:*` pattern
- **Non-blocking:** SCAN doesn't block Redis operations (unlike KEYS)
- **Safety limits:** Prevents infinite loops with reasonable bounds

### Error Handling

All endpoints include comprehensive error handling:

- **400 Bad Request:** Invalid parameters (e.g., empty service name)
- **404 Not Found:** Service mapping doesn't exist
- **501 Not Implemented:** Cache is not enabled
- **503 Service Unavailable:** Mapper not initialized
- **500 Internal Server Error:** Unexpected errors

## Testing

### Manual Testing

Start the service:
```bash
cd python-services/ai-clientes
python3 main.py
```

Test the endpoints:
```bash
# Health check
curl http://localhost:8001/admin/service-mapping/health

# Refresh cache
curl -X POST http://localhost:8001/admin/service-mapping/cache/refresh/inyección
```

### Automated Testing

Run the example script:
```bash
python3 api/example_usage.py
```

## Monitoring

### Logs

The API logs all operations:
- Cache invalidation events: `✅ Invalidated cache key: service_mapping:inyección`
- Cache misses: `ℹ️ No cache entry found for service: xyz`
- Errors: `❌ Error refreshing cache: ...`

### Metrics

To monitor cache hit/miss rates, integrate with the existing `CacheManager` from `core.cache`:

```python
from core.cache import CacheManager

# The mapper already uses Redis cache
# To get detailed metrics, you can query the cache stats endpoint
response = requests.get(f"{BASE_URL}/cache/stats")
```

## Security Considerations

**IMPORTANT:** This API currently does not include authentication/authorization.

For production deployment, consider adding:

1. **API Key Authentication:**
   ```python
   from fastapi import Security, HTTPException, Header
   API_KEY = Header(...)

   async def verify_api_key(api_key: str = Security(API_KEY)):
       if api_key != os.getenv("ADMIN_API_KEY"):
           raise HTTPException(status_code=403, detail="Invalid API key")
   ```

2. **IP Whitelisting:**
   - Restrict access to known admin IPs
   - Use nginx or similar reverse proxy

3. **Rate Limiting:**
   - Prevent abuse with rate limiting
   - Use `slowapi` or similar middleware

4. **Audit Logging:**
   - Log all admin operations
   - Include timestamps, users, and actions

## Troubleshooting

### Service returns 503 Service Unavailable

**Cause:** ServiceProfessionMapper not initialized

**Solution:**
1. Check if Supabase is configured correctly
2. Verify the service logs for initialization errors
3. Ensure Redis is connected

### Cache refresh returns "Cache is not enabled"

**Cause:** Redis cache is not configured

**Solution:**
1. Check if Redis is running: `docker ps | grep redis`
2. Verify Redis configuration in settings
3. Check connection: `await redis_client.redis_client.ping()`

### No cache entries found

**Cause:** No services have been cached yet

**Solution:**
1. Make a query to trigger caching: Use the main search API
2. Wait for the first service lookup to occur
3. Check cache stats again

## Future Enhancements

Potential improvements for future versions:

1. **Bulk Operations:**
   - Refresh multiple services in one request
   - Batch cache invalidation

2. **Cache Warming:**
   - Pre-load frequently used mappings
   - Scheduled refresh operations

3. **Detailed Metrics:**
   - Per-service hit/miss rates
   - Cache eviction statistics
   - Performance metrics

4. **Advanced Monitoring:**
   - Prometheus metrics integration
   - Grafana dashboards
   - Alert on cache degradation

## Related Files

- `/home/du/produccion/tinkubot-microservices/python-services/ai-clientes/api/service_profession_mapping_admin.py` - Main API implementation
- `/home/du/produccion/tinkubot-microservices/python-services/ai-clientes/services/service_profession_mapper.py` - Mapper service
- `/home/du/produccion/tinkubot-microservices/python-services/ai-clientes/main.py` - FastAPI application
- `/home/du/produccion/tinkubot-microservices/python-services/ai-clientes/core/cache.py` - Cache manager

## Support

For issues or questions, please check:
1. Service logs: Check stderr/stdout for detailed error messages
2. Health check: `GET /admin/service-mapping/health`
3. Cache stats: `GET /admin/service-mapping/cache/stats`
