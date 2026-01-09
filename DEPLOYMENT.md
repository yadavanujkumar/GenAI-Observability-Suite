# Deployment Guide

## Local Development

### Quick Start

1. **Clone and setup**
   ```bash
   cd /workspaces/GenAI-Observability-Suite
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env with your API keys:
   # - OPENAI_API_KEY
   # - ANTHROPIC_API_KEY (optional)
   ```

3. **Start services**
   ```bash
   chmod +x start.sh
   ./start.sh
   ```

4. **Access endpoints**
   - API: http://localhost:8000
   - Docs: http://localhost:8000/docs
   - Dashboard: http://localhost:8501

---

## Docker Compose (Recommended)

### Single command startup

```bash
# Copy and edit environment
cp .env.example .env

# Start all services
docker-compose up -d

# View logs
docker-compose logs -f gateway
docker-compose logs -f dashboard

# Stop all services
docker-compose down
```

### Individual service logs
```bash
docker-compose logs redis
docker-compose logs qdrant
docker-compose logs gateway
docker-compose logs dashboard
```

### Rebuild after code changes
```bash
docker-compose build --no-cache
docker-compose up -d
```

---

## Production Deployment

### Using Kubernetes

1. **Create namespace**
   ```bash
   kubectl create namespace llm-gateway
   ```

2. **Deploy Redis**
   ```bash
   kubectl apply -f k8s/redis.yaml -n llm-gateway
   ```

3. **Deploy Qdrant**
   ```bash
   kubectl apply -f k8s/qdrant.yaml -n llm-gateway
   ```

4. **Deploy Gateway (with secrets)**
   ```bash
   # Create secret for API keys
   kubectl create secret generic llm-keys \
     --from-literal=OPENAI_API_KEY='sk-...' \
     --from-literal=ANTHROPIC_API_KEY='sk-...' \
     -n llm-gateway
   
   # Deploy
   kubectl apply -f k8s/gateway.yaml -n llm-gateway
   ```

5. **Deploy Dashboard**
   ```bash
   kubectl apply -f k8s/dashboard.yaml -n llm-gateway
   ```

6. **Check status**
   ```bash
   kubectl get pods -n llm-gateway
   kubectl get svc -n llm-gateway
   ```

### Using AWS ECS

1. **Push images to ECR**
   ```bash
   # Create ECR repository
   aws ecr create-repository --repository-name llm-gateway
   aws ecr create-repository --repository-name llm-dashboard
   
   # Login
   aws ecr get-login-password --region us-east-1 | \
     docker login --username AWS --password-stdin <account-id>.dkr.ecr.us-east-1.amazonaws.com
   
   # Push
   docker tag llm-gateway:latest <account-id>.dkr.ecr.us-east-1.amazonaws.com/llm-gateway:latest
   docker push <account-id>.dkr.ecr.us-east-1.amazonaws.com/llm-gateway:latest
   ```

2. **Create ECS task definition** - use `ecs-task-definition.json`

3. **Create ECS service**
   ```bash
   aws ecs create-service \
     --cluster llm-gateway-cluster \
     --service-name llm-gateway \
     --task-definition llm-gateway:1 \
     --desired-count 2 \
     --launch-type FARGATE
   ```

### Using Cloud Run (Google Cloud)

```bash
# Build and push
gcloud builds submit --tag gcr.io/PROJECT_ID/llm-gateway

# Deploy
gcloud run deploy llm-gateway \
  --image gcr.io/PROJECT_ID/llm-gateway \
  --platform managed \
  --region us-central1 \
  --set-env-vars="OPENAI_API_KEY=sk-..." \
  --memory 2Gi \
  --cpu 2
```

---

## Performance Tuning

### FastAPI Optimization
```bash
# Increase worker count
uvicorn app.main:app --workers 4 --host 0.0.0.0 --port 8000
```

### Redis Optimization
```bash
# Increase maxmemory and eviction policy
redis-cli CONFIG SET maxmemory 2gb
redis-cli CONFIG SET maxmemory-policy allkeys-lru
```

### Qdrant Optimization
```bash
# Increase index snapshots for durability
# Edit docker-compose.yml to add:
# environment:
#   - QDRANT_TELEMETRY_DISABLED=true
```

---

## Monitoring

### Using Prometheus + Grafana

1. **Add metrics export to FastAPI**
   ```python
   from prometheus_client import Counter, Histogram
   
   request_count = Counter('llm_gateway_requests_total', 'Total requests')
   response_time = Histogram('llm_gateway_response_ms', 'Response time')
   ```

2. **Configure Prometheus**
   ```yaml
   # prometheus.yml
   global:
     scrape_interval: 15s
   scrape_configs:
     - job_name: 'llm-gateway'
       static_configs:
         - targets: ['localhost:8000']
   ```

3. **Run Grafana**
   ```bash
   docker run -d -p 3000:3000 grafana/grafana
   ```

---

## Scaling

### Horizontal Scaling
```bash
# Docker Compose - scale gateway
docker-compose up -d --scale gateway=3
```

### Load Balancing
```bash
# Using Nginx
upstream gateway {
    server gateway-1:8000;
    server gateway-2:8000;
    server gateway-3:8000;
}

server {
    listen 80;
    location /chat {
        proxy_pass http://gateway;
    }
}
```

---

## Troubleshooting

### Gateway won't start
```bash
# Check logs
docker-compose logs gateway

# Common issues:
# 1. Port 8000 already in use
# 2. Missing .env file
# 3. Invalid API keys
```

### Redis connection errors
```bash
# Check Redis is running
docker-compose logs redis

# Flush cache if needed
docker-compose exec redis redis-cli FLUSHALL
```

### Qdrant connection errors
```bash
# Check Qdrant is running
docker-compose logs qdrant

# Reset collections if needed
curl -X DELETE http://localhost:6333/collections/semantic_cache
```

---

## Backup & Recovery

### Backup data
```bash
# Redis
docker-compose exec redis redis-cli BGSAVE
docker cp llm-redis:/data/dump.rdb ./backups/redis-backup.rdb

# Qdrant
docker cp llm-qdrant:/qdrant/storage ./backups/qdrant-backup

# Logs
cp data/interactions.jsonl ./backups/interactions-$(date +%s).jsonl
```

### Restore
```bash
# From backed up data
docker cp ./backups/redis-backup.rdb llm-redis:/data/dump.rdb
docker cp ./backups/qdrant-backup llm-qdrant:/qdrant/storage
```

---

## Security

### Best Practices

1. **Use secrets management**
   ```bash
   # Don't commit .env files
   echo ".env" >> .gitignore
   
   # Use Docker secrets (Swarm) or Kubernetes secrets
   ```

2. **API key rotation**
   ```bash
   # Periodically regenerate keys on provider platforms
   # Update in secrets manager
   ```

3. **Network isolation**
   ```bash
   # Use private networks only for inter-service communication
   # Expose gateway behind reverse proxy with SSL/TLS
   ```

4. **Rate limiting**
   ```python
   from slowapi import Limiter
   from slowapi.util import get_remote_address
   
   limiter = Limiter(key_func=get_remote_address)
   
   @app.post("/chat")
   @limiter.limit("100/minute")
   async def chat(...):
       ...
   ```

---

## Cost Optimization

### Reduce API calls
- Higher cache hit rate target (40-50%)
- Batch similar requests
- Use fallback to cheaper models

### Monitor costs
```python
# In observability_logger.py
cost_per_token = {
    "gpt-4o-mini": 0.000015,
    "gpt-3.5-turbo": 0.0000005,
}

# Track in logging
```

---

## Support

For deployment issues, refer to individual service documentation:
- [FastAPI](https://fastapi.tiangolo.com)
- [Redis](https://redis.io/documentation)
- [Qdrant](https://qdrant.tech/documentation)
- [Streamlit](https://docs.streamlit.io)
