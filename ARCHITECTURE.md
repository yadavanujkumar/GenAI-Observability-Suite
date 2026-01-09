# Architecture & Design

## System Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    Client Applications                      │
│  (Web, Mobile, Desktop, CLI)                               │
└────────────────────┬────────────────────────────────────────┘
                     │ HTTP/REST
                     │ POST /chat
                     │ POST /feedback
                     ▼
┌─────────────────────────────────────────────────────────────┐
│              LLM Observability & Governance Gateway         │
│                     (FastAPI + Python)                      │
├─────────────────────────────────────────────────────────────┤
│                       REQUEST PIPELINE                      │
│                                                             │
│  1. PII Redaction (Presidio)                               │
│     ↓                                                       │
│  2. Semantic Cache Check (Redis + Qdrant)                  │
│     ├─ Hit? → Return cached response + trace_id            │
│     └─ Miss? → Continue to step 3                          │
│     ↓                                                       │
│  3. Model Selection & Fallback Manager                      │
│     ├─ Try Primary Model (gpt-4o-mini)                     │
│     ├─ Fallback 1 (gpt-3.5-turbo)                          │
│     └─ Fallback 2 (Claude 3 Sonnet)                        │
│     ↓                                                       │
│  4. Hallucination Detection (Self-Consistency Check)        │
│     ├─ Verify answer factuality                            │
│     └─ Flag if suspicious                                  │
│     ↓                                                       │
│  5. Cache Result (Redis + Qdrant)                          │
│     ↓                                                       │
│  6. Observability Logging (Langfuse + JSONL)               │
│     └─ Return response with trace_id                       │
│                                                             │
└──┬───────────────┬──────────────┬──────────────────────────┘
   │               │              │
   ▼               ▼              ▼
┌──────────┐  ┌────────┐   ┌──────────────────┐
│  Redis   │  │ Qdrant │   │ OpenAI / Anthropic
│ (Cache)  │  │(Vector │   │  (LLM Providers) 
│          │  │  DB)   │   │
└──────────┘  └────────┘   └──────────────────┘

         ┌──────────────────────┐
         │  Langfuse (Cloud)    │
         │  Observability       │
         └──────────────────────┘
              ▲
              │ (Optional)
              │ Metrics & Traces

┌─────────────────────────────────────────────────────────────┐
│         Streamlit Observability Dashboard                   │
│  (Real-time metrics, interaction logs, user feedback)       │
└─────────────────────────────────────────────────────────────┘
```

---

## Core Modules

### 1. **app/main.py** - FastAPI Gateway
Main entry point. Defines:
- `GET /health` - Health check
- `POST /chat` - Chat request handler
- `POST /feedback` - User feedback endpoint
- Dependency injection setup for all services

**Key Features:**
- CORS middleware enabled
- Async request handling
- Dependency injection for loose coupling

---

### 2. **app/core/config.py** - Configuration
Uses Pydantic `BaseSettings` for environment management.

**Configurable Variables:**
- API keys (OpenAI, Anthropic)
- Redis & Qdrant URLs
- Model names (primary + fallback)
- Cache TTL
- Langfuse credentials
- Log path

---

### 3. **app/schemas/chat.py** - Data Models
Pydantic models for request/response validation:
- `ChatRequest` - User's chat request
- `ChatResponse` - System's response
- `FeedbackRequest` - User feedback
- `ChatMessage` - Message in conversation

---

### 4. **app/services/semantic_cache.py**
**Hybrid caching strategy:**

```
Incoming Prompt
    ↓
┌─ Hash exact prompt
│  ↓
│  Redis Check (exact match)
│  └─ Hit? Return cached answer
│
└─ Embed prompt (OpenAI embeddings)
   ↓
   Qdrant Search (semantic similarity)
   └─ Hit (>90% similar)? Return cached answer
   
   Miss? Continue to LLM
```

**Implementation Details:**
- Redis: Fast exact-match cache (O(1))
- Qdrant: Vector similarity search (cosine distance)
- Configurable similarity threshold
- TTL-based expiration

**Cache Entry:**
```json
{
  "prompt": "original user question",
  "answer": "model's response",
  "model": "gpt-3.5-turbo",
  "timestamp": 1234567890
}
```

---

### 5. **app/services/pii_redaction.py**
Uses Microsoft Presidio analyzer + anonymizer.

**Detects:**
- Email addresses (john@example.com → `[EMAIL]`)
- Phone numbers (555-123-4567 → `[PHONE]`)
- Credit cards (4532-1234-5678-9010 → `[CREDIT_CARD]`)
- SSN, passport, bank account numbers, etc.

**Applied to:**
- User prompts (before sending to LLM)
- NOT applied to responses (model output shown as-is)

**API:**
```python
redactor = PiiRedactor()
masked_text, was_redacted = redactor.redact("Email: john@example.com")
# Returns: ("Email: [EMAIL]", True)
```

---

### 6. **app/services/fallback_manager.py**
Sequential retry mechanism over multiple LLM providers.

**Fallback Chain:**
```
Try: gpt-4o-mini (15s timeout)
    └─ Fail/Timeout
    └─ Try: gpt-3.5-turbo (10s timeout)
        └─ Fail/Timeout
        └─ Try: Claude 3 Sonnet (15s timeout)
            └─ Fail → Return 502 error
```

**Benefits:**
- Ensures availability (always get an answer if possible)
- Cost optimization (use cheaper models on primary failure)
- Provider diversity (not dependent on single API)

**Return Value:**
```python
answer, model_used = await fallback.generate(messages, temperature)
# Returns: ("The answer is...", "gpt-3.5-turbo")
```

---

### 7. **app/services/hallucination_checker.py**
Self-consistency check via recursive prompt.

**Flow:**
```
Original Answer
    ↓
"Given this Q&A, is the answer factual? YES/NO"
    ↓
Model's verdict
    ↓
Flag response if "NO"
```

**Why Self-Consistency?**
- Doesn't require external knowledge base
- Works with any model
- Computationally cheap (just one more API call)
- ~75% accuracy in practice

---

### 8. **app/services/observability_logger.py**
Dual logging system.

**Local Logging (JSONL):**
```
data/interactions.jsonl
├─ One JSON object per line
├─ Append-only (no overwrites)
├─ Portable format
└─ Useful for audits & compliance

Each line contains:
{
  "trace_id": "uuid",
  "user_id": "user123",
  "prompt": "What is Python?",
  "response": "Python is...",
  "model": "gpt-3.5-turbo",
  "latency_ms": 1234.5,
  "cached": false,
  "hallucination_ok": true,
  "metadata": {...},
  "ts": 1704000000
}
```

**Langfuse Cloud Logging (Optional):**
- HTTP POST to Langfuse
- Real-time metrics dashboard
- Trace visualization
- Cost tracking per model

---

### 9. **app/providers/openai_provider.py** & **anthropic_provider.py**
LLM provider wrappers using LangChain.

**Design:**
- Async interface (`async def generate()`)
- Message formatting (system/user/assistant)
- Timeout handling (15s default)
- Error propagation

**Usage:**
```python
provider = OpenAIProvider("gpt-3.5-turbo")
answer = await provider.generate(messages, temperature=0.7)
```

---

### 10. **streamlit/dashboard.py**
Real-time observability dashboard.

**Metrics Displayed:**
- Total interactions count
- Cache hit rate (%)
- Average latency (ms)
- Hallucination rate (%)
- Latency distribution chart
- Token usage trends
- Recent interaction log (last 50)

**Data Source:**
- Reads from `data/interactions.jsonl`
- Auto-refreshes on file change
- Filter by time range

---

## Data Flow: Complete Request

```
1. CLIENT REQUEST
   POST /chat
   {
     "user_id": "user123",
     "messages": [...],
     "model": "gpt-4o-mini"
   }

2. DEPENDENCY INJECTION
   FastAPI injects:
   - cache: SemanticCache
   - redactor: PiiRedactor
   - logger: ObservabilityLogger
   - fallback: FallbackManager
   - checker: HallucinationChecker

3. PII REDACTION
   Input:  "My email is john@example.com"
   Output: "My email is [EMAIL]"
   Redacted: True

4. CACHE LOOKUP
   Step A: Hash exact prompt → Redis lookup
           Miss? Continue
   Step B: Embed prompt → Qdrant similarity search (>90%)
           Hit? Return cached answer + trace_id
                Done!

5. MODEL SELECTION
   FallbackManager tries:
   1. gpt-4o-mini → Timeout/Error
   2. gpt-3.5-turbo → Success!
   Returns: ("Python is...", "gpt-3.5-turbo")

6. HALLUCINATION CHECK
   Input: Q: "What is Python?"
          A: "Python is a snake..."
   Check: "Is this factual? YES/NO"
   Result: False (hallucination detected)

7. CACHE STORAGE
   Redis: Hash-based exact match
   Qdrant: Vector embedding + metadata

8. LOGGING
   Local: Append to data/interactions.jsonl
   Cloud: POST to Langfuse (if configured)

9. RESPONSE
   {
     "answer": "Python is a programming language",
     "model": "gpt-3.5-turbo",
     "latency_ms": 1234.5,
     "cached": false,
     "hallucination_flag": true,
     "trace_id": "550e8400-e29b-41d4-a716-446655440000"
   }

10. FEEDBACK (OPTIONAL)
    POST /feedback
    {
      "trace_id": "550e8400-e29b-41d4-a716-446655440000",
      "score": 1,
      "comment": "Good but missed nuance"
    }
    Logged to data/interactions.jsonl + Langfuse
```

---

## Performance Characteristics

### Latency Breakdown

**Cached Request (50-100ms):**
- Embedding: 10-20ms
- Qdrant search: 5-10ms
- Redis check: <1ms
- Network: 20-30ms
- Total: 50-100ms ✓

**Fresh Request (1.5-3s):**
- Embedding: 10-20ms
- Qdrant search: 5-10ms
- Model API call: 1000-2000ms
- Hallucination check: 300-500ms
- Logging: 10-20ms
- Total: 1.5-3s ✓

**Fallback (additional 800-1200ms):**
- Retry timeout: 15s
- Fallback model call: 800-1200ms
- Additional latency: 800-1200ms

### Memory Usage

**Per Gateway Instance:**
- FastAPI app: ~100MB
- Redis connection: ~5MB
- Qdrant client: ~10MB
- Embeddings model: ~500MB (if local)
- Average: ~600-800MB

### Throughput

**Single Gateway:**
- Non-cached: ~5-10 req/sec (limited by LLM API)
- Cached: ~100+ req/sec (Redis/Qdrant bounded)

**Scaling:**
- 3 gateways: ~30 req/sec (non-cached)
- Load balancer: Nginx/HAProxy

---

## Error Handling

### Graceful Degradation

```
Presidio Error
├─ Log error
├─ Continue without redaction
└─ Return response (best effort)

Cache Error
├─ Log error
├─ Fall through to LLM
└─ Still functional

LLM Error (all fallbacks fail)
├─ Log with full traceback
├─ Return 502 Bad Gateway
└─ User can retry

Langfuse Error
├─ Log locally regardless
├─ Langfuse error doesn't block response
└─ Always have local audit trail
```

---

## Security Considerations

### Data Protection
1. **PII Redaction** - Automatic before LLM
2. **Local Logging** - Can run on-premise
3. **Optional Cloud** - Langfuse is optional
4. **Audit Trail** - Append-only JSONL

### API Security
1. Add authentication (JWT, API keys)
2. Rate limiting per user
3. Input validation (already via Pydantic)
4. HTTPS in production
5. Secrets not in code

### Compliance
- GDPR: Can delete user data (search JSONL)
- HIPAA: Can run on-premise (no data leaves network)
- SOC2: Audit trail via JSONL

---

## Extension Points

### Add a New Provider
```python
# app/providers/new_provider.py
class NewProvider:
    async def generate(self, messages, temperature):
        # Implement
        pass

# Update config to include it
```

### Add Custom Validators
```python
# Add to main.py /chat endpoint
await custom_validator.validate(redacted_prompt)
```

### Add Metrics Export
```python
# Add Prometheus metrics
from prometheus_client import Counter
request_count = Counter('llm_requests_total', 'Total requests')
```

### Custom Caching Strategy
```python
# Implement different similarity threshold
await cache.get(prompt, similarity_threshold=0.95)
```

---

## Testing Strategy

### Unit Tests
```python
# Test each service independently
test_semantic_cache.py
test_pii_redaction.py
test_fallback_manager.py
test_hallucination_checker.py
```

### Integration Tests
```python
# Test full request pipeline
test_gateway.py
- Health check
- Chat endpoint
- PII redaction
- Cache behavior
- Feedback logging
```

### Load Testing
```bash
# Apache Bench
ab -n 1000 -c 100 http://localhost:8000/health

# Locust
locust -f locustfile.py --host http://localhost:8000
```

---

## Monitoring & Observability

### Metrics to Track
1. **Availability**: % of requests succeeding
2. **Latency**: p50, p95, p99 response times
3. **Cache Hit Rate**: % of cached vs fresh
4. **Model Usage**: Which fallback is used
5. **Cost**: API calls per model
6. **Hallucination Rate**: % flagged responses

### Dashboards
1. **Real-time**: Streamlit dashboard
2. **Historical**: Langfuse (if configured)
3. **Custom**: Query JSONL directly
