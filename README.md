# Pulse AI - Job Discovery & Alert Engine

A high-reliability modular monolith for ingesting jobs from company ATS public feeds, normalizing, deduplicating across sources, verifying availability, generating semantic vector embeddings (`pgvector`), matching to candidate profiles, and dispatching alerts.

---

## Architecture Pipeline

```text
Scheduler -> Discovery (Greenhouse, Ashby) -> Normalize -> Deduplicate -> Verify -> Embed -> Match -> Rank -> Outbox -> Dispatch
```

---

## Features Implemented

### Milestone 1: Ingestion & Reconciliation
* **ATS Connectors**: Greenhouse public board API with timeouts, jittered exponential backoff, and domain token-bucket rate limiting.
* **HTML Normalizer**: Sanitizes HTML into clean text, extracts locations, and classifies `remote_type`, `seniority`, and `employment_type`.
* **Deterministic Hashing**: SHA-256 `content_hash` over canonical fields to skip unchanged database records.
* **Watermark Disappearance Detection**: Detects removed jobs in $O(1)$ query without table-locking `NOT IN` queries and marks them closed.
* **Celery Scheduler**: Periodic due-source polling with optimistic leasing (`FOR UPDATE SKIP LOCKED`).

### Milestone 2: Deduplication, Verification & Vector Embeddings
* **Cross-Source Deduplication & Clustering**:
  * Normalizes company names (stripping legal entity suffixes) and titles.
  * Generates a semantic `dedup_fingerprint`.
  * Clusters identical jobs from different sources under a master `JobCluster` (`primary_job_id`, `job_count`), preserving all apply URLs and metadata.
* **Second ATS Connector (Ashby)**:
  * Public board JSON API connector for Ashby (`api.ashbyhq.com`), tested live with companies like Linear.
* **Live Job Verification (Still Open Check)**:
  * Fast HTTP verifier that detects 404/410 status codes and checks HTML for ATS closure phrases (*"no longer accepting applications"*, *"position has been filled"*, *"this job has expired"*).
  * Automatically closes dead jobs upon verification.
* **Vector Embeddings Subsystem (`pgvector`)**:
  * Pluggable `BaseEmbeddingProvider` interface.
  * Default zero-cost local provider: `FastEmbed` (`sentence-transformers/all-MiniLM-L6-v2`, 384 dimensions) running on CPU.
  * HNSW index (`vector_cosine_ops`) for sub-millisecond approximate nearest neighbor (ANN) vector search directly in PostgreSQL.
  * Semantic vector search endpoint: `GET /api/jobs/search?q=...`.

### Milestone 3: Candidate Profiles, Reverse Matching, Multi-Factor Ranking & Outbox Dispatch
* **Candidate Profiles & Resume Parsing**:
  * Upload resume as text or PDF via `pypdf`.
  * Automatic technical skill extraction (languages, databases, cloud, messaging frameworks) and experience years detection.
  * Fast candidate vector embedding generation capturing both role intent and technical profile.
* **Reverse Matching Engine**:
  * Efficient candidate-to-job matching with cluster deduplication (delivers canonical cluster job).
  * Ignores dismissed jobs via candidate feedback tracking.
* **Multi-Factor Ranking Formula**:
  * **Semantic Vector Cosine Similarity (60%)**: Alignment between candidate profile vector and job description vector.
  * **Title Keyword Overlap (25%)**: Exact and token overlap matching candidate target roles.
  * **Exponential Recency Decay (15%)**: $e^{-0.1 \times \text{days}}$, rewarding newly published roles.
  * **Hard Constraint Filters**: Rejects mismatched seniorities and remote policies before ranking.
* **Transactional Outbox Notification Pattern**:
  * Guaranteed delivery with `notification_outbox` table and exponential backoff retry logic.
  * **Telegram Channel Dispatcher**: Sends formatted job alert cards with direct apply links and match reasons.
  * **Email Channel Dispatcher**: SMTP-ready delivery for rich HTML daily digests.
* **Scheduled 9 AM Daily Digest**:
  * Celery Beat cron task (`run_9am_daily_digest_task`) that periodically evaluates candidate alerts, computes top matches, and queues notifications in the outbox.

---

## Quickstart

### 1. Run with Docker Compose
```bash
docker-compose up -d --build
```
* **Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs)
* **Health Check**: [http://localhost:8000/health](http://localhost:8000/health)

### 2. Run Test Suite
```bash
pytest -v
```
*(All 34 unit and integration tests run in ~9 seconds)*

---

## API Endpoints

### Sources & Jobs
| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/health` | Service and database health check |
| `POST` | `/api/sources/` | Register an ATS source (`greenhouse` or `ashby`) |
| `GET` | `/api/sources/` | List all registered sources and crawl health |
| `POST` | `/api/sources/{id}/crawl` | Trigger an immediate source crawl |
| `GET` | `/api/jobs/` | List canonical jobs with filters (`status`, `company`, `remote_type`, `seniority`, `verification_status`) |
| `GET` | `/api/jobs/search` | **Semantic vector search** using pgvector cosine similarity |
| `POST` | `/api/jobs/deduplicate` | Trigger batch cross-source deduplication & clustering |
| `POST` | `/api/jobs/verify` | Trigger batch link availability verification |
| `POST` | `/api/jobs/embed` | Trigger batch vector embedding generation |

### Candidates, Matching & Outbox (Milestone 3)
| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/api/users/` | Register a candidate with target roles, seniority, and preferences |
| `GET` | `/api/users/{id}` | Retrieve candidate profile, skills, and embedding status |
| `PUT` | `/api/users/{id}/profile` | Update candidate job search criteria, resume, and preferences |
| `POST` | `/api/users/{id}/resume` | Upload a candidate resume (PDF file or raw text) |
| `GET` | `/api/users/{id}/matches` | **Reverse match** active jobs scored and ranked for this candidate |
| `POST` | `/api/users/{id}/feedback` | Record user interaction (`applied`, `saved`, `dismissed`) |
| `POST` | `/api/users/{id}/trigger-digest` | Trigger an on-demand match and dispatch an alert to Telegram/Email |

