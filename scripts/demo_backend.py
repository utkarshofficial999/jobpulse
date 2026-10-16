"""
Pulse AI - Live Backend Pipeline Demo
Demonstrates:
1. Registering live sources (Stripe & Linear)
2. Ingesting jobs via Greenhouse and Ashby APIs
3. Deduplicating & clustering identical jobs
4. Generating vector embeddings
5. Semantic vector search query
"""
from src.core.database import SessionLocal, Base, engine
from src.core.logging import setup_logging
from src.modules.sources.repository import SourceRepository
from src.modules.discovery.service import crawl_source
from src.modules.deduplication.service import DeduplicationService
from src.modules.embeddings.service import EmbeddingService


def main():
    setup_logging()
    print("=" * 60)
    print("🚀 PULSE AI: LIVE BACKEND DEMO")
    print("=" * 60)

    # Ensure tables exist
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        # 1. Register Sources
        print("\n[Step 1] Registering ATS Sources...")
        src_stripe = SourceRepository.create(
            db=db,
            name="Stripe",
            connector_type="greenhouse",
            config={"board_token": "stripe", "company_name": "Stripe"},
        )
        print(f"  ✓ Created Stripe Greenhouse Source (id={src_stripe.id})")

        src_linear = SourceRepository.create(
            db=db,
            name="Linear",
            connector_type="ashby",
            config={"board_token": "linear", "company_name": "Linear"},
        )
        print(f"  ✓ Created Linear Ashby Source (id={src_linear.id})")

        # 2. Ingest Live Jobs
        print("\n[Step 2] Crawling Live Jobs over the Wire...")
        metrics_stripe = crawl_source(src_stripe.id, db=db)
        print(f"  ✓ Stripe: Discovered {metrics_stripe.discovered} jobs (Upserted {metrics_stripe.new_upserted}) in {metrics_stripe.duration_ms}ms")

        metrics_linear = crawl_source(src_linear.id, db=db)
        print(f"  ✓ Linear: Discovered {metrics_linear.discovered} jobs (Upserted {metrics_linear.new_upserted}) in {metrics_linear.duration_ms}ms")

        # 3. Cross-Source Deduplication
        print("\n[Step 3] Running Cross-Source Deduplication & Clustering...")
        clustered = DeduplicationService.batch_deduplicate(db, limit=500)
        print(f"  ✓ Clustered {clustered} jobs into deduplicated canonical groups.")

        # 4. Generate Vector Embeddings
        print("\n[Step 4] Generating Semantic Vector Embeddings (384-dim FastEmbed)...")
        embedded = EmbeddingService.generate_batch(db, batch_size=20)
        print(f"  ✓ Generated vector embeddings for top {embedded} jobs.")

        # 5. Semantic Vector Search
        query = "senior distributed systems backend engineer"
        print(f"\n[Step 5] Running Semantic Vector Search for: '{query}'")
        results = EmbeddingService.search_similar_jobs(db, query=query, limit=3)

        print("\nTop Semantic Matches:")
        for idx, (job, score) in enumerate(results, start=1):
            print(f"  {idx}. [{score:.2f} Match] {job.title} @ {job.company}")
            print(f"     Locations: {job.locations} | Remote: {job.remote_type} | Seniority: {job.seniority}")
            print(f"     Apply URL: {job.apply_url}\n")

        print("=" * 60)
        print("✅ Pipeline executed successfully!")
        print("=" * 60)

    finally:
        db.close()


if __name__ == "__main__":
    main()
