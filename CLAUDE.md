# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

LLM-based personalized product recommendation system using Amazon Reviews (Industrial_and_Scientific) dataset. The system uses Qwen2.5-3B with SFT+GRPO fine-tuning and RQ-VAE for semantic ID generation.

## Tech Stack

**Backend:** FastAPI, Elasticsearch 8.x, Redis 7.x, Milvus (Lite), Transformers + PEFT, Sentence-Transformers, Pydantic-Settings, structlog
**Frontend:** React 18, TypeScript 5, Vite 5, Tailwind CSS 3, shadcn/ui, TanStack Query 5, Zustand 4, React Router 6

## Architecture

```
Frontend (React/Vite :5173) → Nginx → FastAPI (:8000)
                                          ├─ SID Service (ASIN ↔ Semantic ID mapping)
                                          ├─ Recommender Inference (Qwen2.5-3B + LoRA)
                                          ├─ Embedding Service (bge-base-en-v1.5)
                                          ├─ Vector Service (Milvus Lite)
                                          └─ Elasticsearch (:9200) + Redis (:6379)
```

**Recommendation Pipeline:**
1. User history ASINs → SID sequence (via SIDService)
2. SID sequence → Model inference → Candidate SIDs (via RecommenderInference)
3. Candidate SIDs → ASINs (via SIDService)
4. ASINs → Product details (via ES mget)
5. Return sorted Top-K products

## Common Commands

### Backend Setup
```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Run Backend
```bash
cd backend
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

### Run Frontend
```bash
cd frontend
npm install
npm run dev  # Starts on :5173
```

### Tests
```bash
# Backend tests
cd backend
pytest tests/unit/ -v           # Unit tests
pytest tests/integration/ -v    # Integration tests
pytest --cov=. --cov-report=term-missing  # With coverage

# Frontend tests
cd frontend
npm run test                    # Vitest
npm run test:coverage
```

### Docker Stack
```bash
docker-compose up -d            # Start all services
docker-compose down             # Stop all services
docker-compose logs -f api      # View API logs
```

### Data Processing
```bash
cd backend
python data/scripts/preprocess_products.py
python data/scripts/preprocess_interactions.py
python data/scripts/build_sid_mapping.py
```

### Elasticsearch
```bash
cd backend
python es_client/scripts/create_index.py
python es_client/scripts/bulk_index_products.py
```

### Milvus Embeddings
```bash
cd backend
python scripts/build_embeddings.py    # Build product embeddings into Milvus
```

## Key Configuration

- Backend config: `backend/config/settings.py` (uses Pydantic-Settings, reads from `.env`)
- ES index: `industrial_products`
- SID mapping: `backend/data/processed/sid_mapping.json`
- Model checkpoints: `backend/models/checkpoints/` (not in git)

## Data Files (Root)

- `Industrial_and_Scientific.json.gz` - User interaction data
- `meta_Industrial_and_Scientific.json.gz` - Product metadata

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/recommend` | Get personalized recommendations |
| GET | `/api/v1/products/{asin}` | Get product details |
| GET | `/api/v1/products/search` | Search products (`mode=keyword\|vector\|hybrid`) |
| POST | `/api/v1/behavior` | Report user behavior |
| GET | `/health` | Health check |
