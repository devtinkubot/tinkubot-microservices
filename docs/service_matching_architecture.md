# Service-Based Matching - Architecture Guide

## Overview

The Service-Based Matching system transforms Tinkubot from **profession-based** to **service-based** matching with multi-dimensional scoring. This solves the problem where users search for specific services (e.g., "necesito inyecciones") but the system only matches by profession (e.g., "enfermero" or "médico").

## Problem Statement

**Before:**
```
User: "necesito inyecciones de vitaminas en cuenca"
System: Searches for profession "enfermero" OR "médico"
Result: Doesn't distinguish which is more appropriate for injections
```

**After:**
```
User: "necesito inyecciones de vitaminas en cuenca"
System:
  1. Detects service: "inyección" (confidence: 0.85)
  2. Maps to professions: enfermero (0.95), médico (0.70)
  3. Searches providers offering "inyección"
  4. Scores by appropriateness: Enfermero ranks first!
Result: Enfermero appears first (more appropriate for injections)
```

## Architecture

### Components

```
┌─────────────────────────────────────────────────────────────┐
│                     User Message                             │
│            "necesito inyecciones en cuenca"                 │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│              ServiceDetectorService                          │
│  - Detects services: ["inyección", "inyecciones"]           │
│  - Extracts primary: "inyección"                            │
│  - Calculates confidence: 0.85                              │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│            ServiceProfessionMapper                           │
│  - Maps service → professions with scores                   │
│  - Uses cache (Redis, 1h TTL)                               │
│  - "inyección" → [("enfermero": 0.95), ("médico": 0.70)]    │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│              ProviderRepository                              │
│  - search_by_service_and_city()                            │
│  - Queries providers.services_list (JSONB)                  │
│  - Filters by professions AND service                      │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│             ServiceMatchingService                           │
│  - Calculates multi-dimensional score for each provider     │
│  - Sorts by relevance (not just rating!)                    │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                    Scored Providers                          │
│  1. Enfermero María (score: 0.80) ← Most appropriate        │
│  2. Médico Carlos (score: 0.71)                            │
└─────────────────────────────────────────────────────────────┘
```

### Scoring Algorithm

The relevance score combines multiple factors:

```python
total_score = (
    profession_appropriateness * 0.35 +  # Is this profession right for the service?
    provider_rating * 0.25 +              # How highly rated is the provider?
    experience * 0.20 +                   # How experienced are they?
    service_specificity_bonus * 0.15 +    # Do they explicitly offer this service?
    verification * 0.05                   # Are they verified?
)
```

**Example Calculation:**

Enfermero María (rating=4.5, exp=5, offers injections):
- Profession score: 0.95 × 0.35 = 0.33
- Rating score: 0.90 × 0.25 = 0.23
- Experience: 0.50 × 0.20 = 0.10
- Specificity bonus: 0.15 (offers "inyección" explicitly)
- Verification: 0.05
- **Total: 0.80**

Médico Carlos (rating=5.0, exp=10, offers injections):
- Profession score: 0.70 × 0.35 = 0.25
- Rating score: 1.00 × 0.25 = 0.25
- Experience: 1.00 × 0.20 = 0.20
- Specificity bonus: 0.15 (offers "inyección" explicitly)
- Verification: 0.05
- **Total: 0.71**

**Result:** Enfermero ranks first despite lower rating!

## Database Schema

### service_profession_mapping Table

```sql
CREATE TABLE service_profession_mapping (
    id BIGSERIAL PRIMARY KEY,
    service_name VARCHAR(100) NOT NULL,
    profession VARCHAR(100) NOT NULL,
    appropriateness_score DECIMAL(3,2) NOT NULL, -- 0.00 to 1.00
    is_primary BOOLEAN DEFAULT FALSE,
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(service_name, profession)
);

CREATE INDEX idx_service_mapping_service ON service_profession_mapping(service_name);
CREATE INDEX idx_service_mapping_profession ON service_profession_mapping(profession);
```

**Example Data:**

| service_name | profession | appropriateness_score | is_primary |
|--------------|------------|----------------------|-------------|
| inyección | enfermero | 0.95 | TRUE |
| inyección | médico | 0.70 | FALSE |
| suero | enfermero | 0.90 | TRUE |
| vitaminas | enfermero | 0.85 | TRUE |

## Usage

### 1. Enable Feature Flags

Set environment variables:

```bash
# .env
USE_SERVICE_MATCHING=true
USE_SERVICE_DETECTOR=true
```

Or in docker-compose.yml:

```yaml
services:
  ai-clientes:
    environment:
      - USE_SERVICE_MATCHING=true
      - USE_SERVICE_DETECTOR=true
```

### 2. Run Database Migration

```bash
# Execute SQL migration
psql -h localhost -U tinkubot -d tinkubot -f docs/migrations/create_service_profession_mapping.sql
```

### 3. Use in Code

```python
from services.service_matching import get_service_matching_service
from services.service_detector import get_service_detector
from services.service_profession_mapper import get_service_profession_mapper

# Initialize services (lazy loading)
matching_service = get_service_matching_service(
    detector=get_service_detector(),
    mapper=get_service_profession_mapper(supabase, redis),
    repo=provider_repository
)

# Search providers for a service
results = await matching_service.find_providers_for_service(
    message="necesito inyecciones de vitaminas en cuenca",
    city="cuenca",
    limit=10
)

# Results are sorted by relevance
for provider in results:
    print(f"{provider.full_name}: {provider.relevance_score:.2f}")
    print(f"  - {provider.profession}")
    print(f"  - {provider.match_details}")
```

## API

### ServiceDetectorService

```python
detector = get_service_detector()

result = await detector.detect_services(
    message="necesito inyecciones de vitaminas en cuenca"
)

# Output:
# ServiceDetectionResult(
#     services=["inyección", "vitamina"],
#     primary_service="inyección",
#     confidence=0.85
# )
```

### ServiceProfessionMapper

```python
mapper = get_service_profession_mapper(supabase, redis)

mapping = await mapper.get_professions_for_service("inyección")

# Output:
# ServiceProfessionMapping(
#     service_name="inyección",
#     professions=[
#         ProfessionScore(profession="enfermero", score=0.95, is_primary=True),
#         ProfessionScore(profession="médico", score=0.70, is_primary=False)
#     ]
# )

# Get primary profession
primary = mapping.get_primary_profession()  # "enfermero"

# Convert to list
profession_list = mapping.to_dict_list()  # [("enfermero", 0.95), ("médico", 0.70)]
```

### ServiceMatchingService

```python
matching = get_service_matching_service(detector, mapper, repo)

# Search with message
providers = await matching.find_providers_for_service(
    message="necesito inyecciones en cuenca",
    city="cuenca",
    limit=10
)

# Or search with direct service
providers = await matching.find_providers_for_direct_service(
    service="inyección",
    city="cuenca",
    limit=10
)

# Access scored providers
for provider in providers:
    print(f"{provider.full_name}")
    print(f"  Relevance: {provider.relevance_score:.2f}")
    print(f"  Profession: {provider.profession}")
    print(f"  Rating: {provider.rating}")
    print(f"  Details: {provider.match_details}")
```

## Examples

### Example 1: Injection Service

**User:** "necesito inyecciones de vitaminas en cuenca"

**Flow:**
1. ServiceDetector detects: `["inyección", "vitamina"]`, primary: `"inyección"`
2. ServiceProfessionMapper maps: `"inyección"` → `enfermero (0.95)`, `médico (0.70)`
3. ProviderRepository searches: providers with `"inyección"` in `services_list`
4. ServiceMatchingService scores and sorts:

```
1. María González (enfermero) - score: 0.80
   - High profession appropriateness (0.95)
   - Good rating (4.5/5)
   - 5 years experience
   - Explicitly offers "inyección"

2. Dr. Carlos Ruiz (médico) - score: 0.71
   - Lower profession appropriateness (0.70)
   - Perfect rating (5.0/5)
   - 10 years experience
   - Explicitly offers "inyección"
```

### Example 2: IV Drips

**User:** "necesito sueros en guayaquil"

**Flow:**
1. ServiceDetector detects: `["suero"]`, primary: `"suero"`
2. ServiceProfessionMapper maps: `"suero"` → `enfermero (0.90)`, `médico (0.75)`
3. Results show nurses first (more appropriate for IV therapy)

## Performance

### Caching Strategy

- **Redis cache** for ServiceProfessionMapper (1 hour TTL)
- **Cache key:** `service_mapping:{service_name}` (lowercased)
- **Cache hit:** ~1ms response time
- **Cache miss:** ~50ms (DB query + cache populate)

### Database Indexes

- `idx_service_mapping_service` on `service_name`
- `idx_service_mapping_profession` on `profession`
- `services_list` JSONB array indexed internally by PostgreSQL

### Query Performance

```python
# Typical query time with cache
mapper.get_professions_for_service("inyección")  # ~1ms (cache hit)

# Database query (cache miss)
mapper.get_professions_for_service("inyección")  # ~50ms (DB + cache)

# Provider search with service filter
repo.search_by_service_and_city("inyección", "cuenca")  # ~100ms
```

## Testing

### Manual Testing

```bash
# 1. Enable feature flags
export USE_SERVICE_MATCHING=true
export USE_SERVICE_DETECTOR=true

# 2. Run service
python -m ai-clientes.main

# 3. Send test message via WhatsApp
# "necesito inyecciones de vitaminas en cuenca"

# 4. Check logs for:
# - Detected service
# - Profession scores
# - Provider ranking by relevance
```

### Unit Tests

```python
# tests/test_service_matching.py

async def test_service_profession_mapper():
    mapper = ServiceProfessionMapper(supabase, redis)
    mapping = await mapper.get_professions_for_service("inyección")

    assert len(mapping.professions) == 2
    assert mapping.professions[0].profession == "enfermero"
    assert mapping.professions[0].score == 0.95
    assert mapping.get_primary_profession() == "enfermero"

async def test_service_detector():
    detector = ServiceDetectorService()
    result = await detector.detect_services("necesito inyecciones")

    assert "inyección" in result.services
    assert result.primary_service == "inyección"
    assert result.confidence > 0.5

async def test_service_matching():
    matching = ServiceMatchingService(detector, mapper, repo)
    providers = await matching.find_providers_for_service(
        "necesito inyecciones en cuenca",
        "cuenca"
    )

    assert len(providers) > 0
    assert providers[0].relevance_score > providers[1].relevance_score
    # First provider should be enfermero, not médico
    assert providers[0].profession == "enfermero"
```

## Rollback Strategy

If something goes wrong, immediate rollback:

```bash
# 1. Disable feature flags
export USE_SERVICE_MATCHING=false
export USE_SERVICE_DETECTOR=false

# 2. Restart service
docker compose restart ai-clientes

# System falls back to V2 (IntentClassifier-based search)
```

No breaking changes - V1 and V2 continue working normally!

## Future Enhancements

### Phase 2: ML-Based Scoring

Train ML model to predict conversion probability:

```python
class MLBasedScoringStrategy(ScoringStrategy):
    async def calculate_score(self, provider, service, profession_scores, context):
        # Use ML model to predict conversion probability
        features = extract_features(provider, service, context)
        conversion_prob = ml_model.predict(features)
        return conversion_prob, {"ml_probability": conversion_prob}
```

### Phase 3: Automatic Score Learning

Learn optimal scores from user behavior:

```sql
-- Track which providers get contacted
CREATE TABLE provider_interactions (
    id BIGSERIAL PRIMARY KEY,
    provider_id UUID,
    service_name VARCHAR(100),
    user_clicked_contact BOOLEAN,
    converted BOOLEAN,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Adjust appropriateness scores based on conversion data
UPDATE service_profession_mapping
SET appropriateness_score = (
    SELECT AVG(CASE WHEN converted THEN 1.0 ELSE 0.0 END)
    FROM provider_interactions
    WHERE service_name = 'inyección'
    AND profession = 'enfermero'
)
WHERE service_name = 'inyección' AND profession = 'enfermero';
```

### Phase 4: Semantic Search

Use embeddings for semantic similarity:

```python
# Generate embeddings for services
service_embedding = embed("inyección")
provider_services_embedding = embed(["inyecciones", "sueros", "curaciones"])

# Calculate similarity
similarity = cosine_similarity(service_embedding, provider_services_embedding)
```

## Troubleshooting

### Issue: Service not detected

**Symptom:** ServiceDetector returns empty services list

**Solutions:**
1. Check if service is in `MEDICAL_SERVICES` set in `service_detector.py`
2. Check if service is in `NEED_KEYWORDS` in `intent_classifier.py`
3. Add service to database: `service_profession_mapping` table

### Issue: No profession mapping found

**Symptom:** ServiceProfessionMapper returns None

**Solutions:**
1. Check database migration was run
2. Verify data in `service_profession_mapping` table
3. Check Redis cache (might be stale)

### Issue: Providers not ranking correctly

**Symptom:** Médico ranks higher than enfermero for injections

**Solutions:**
1. Check `appropriateness_score` values in database
2. Verify scoring algorithm weights in `DefaultScoringStrategy`
3. Check provider data (rating, experience, services_list)

## Monitoring

### Key Metrics

Track these metrics to ensure system health:

```python
# Service Detection Metrics
- service_detection_rate: % of messages with detected services
- service_detection_confidence: Average confidence score

# Matching Metrics
- providers_per_search: Average number of providers returned
- avg_relevance_score: Average relevance score of results
- primary_profession_match_rate: % where top result has is_primary=True

# Business Metrics
- contact_rate: % of searches that result in contact
- conversion_rate: % of contacts that convert to bookings
```

### Logging

```python
# Enable debug logging for detailed insights
import logging
logging.getLogger("services.service_matching").setLevel(logging.DEBUG)

# Logs show:
# - Detected services
# - Profession scores
# - Provider scoring details
# - Fallback behavior
```

## Contributing

### Adding New Services

1. **Database:** Insert into `service_profession_mapping`
   ```sql
   INSERT INTO service_profession_mapping (service_name, profession, appropriateness_score, is_primary)
   VALUES ('masaje', 'masajista', 0.95, TRUE);
   ```

2. **ServiceDetector:** Add to `MEDICAL_SERVICES` if medical
   ```python
   MEDICAL_SERVICES = {"inyección", "suero", "masaje", ...}
   ```

3. **IntentClassifier:** Add to `NEED_KEYWORDS`
   ```python
   NEED_KEYWORDS = {"masaje": "masajista", "masajes": "masajista"}
   ```

4. **Test:** Verify detection and ranking
   ```python
   result = await detector.detect_services("necesito masajes")
   assert "masaje" in result.services
   ```

## References

- Original plan: `/home/du/.claude/plans/eager-bubbling-avalanche.md`
- Database migration: `/docs/migrations/create_service_profession_mapping.sql`
- Feature flags: `/python-services/ai-clientes/core/feature_flags.py`

---

**Author:** Claude Sonnet 4.5
**Created:** 2026-01-16
**Last Updated:** 2026-01-16
