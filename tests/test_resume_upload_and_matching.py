import io
from datetime import datetime, timezone, timedelta
import pytest
from fastapi.testclient import TestClient

from src.api.main import app
from src.core.database import SessionLocal
from src.modules.users.resume_parser import ResumeParser
from src.modules.users.models import User, CandidateProfile
from src.modules.jobs.models import Job
from src.modules.matching.engine import MatchingEngine
from src.modules.matching.ranker import MultiFactorRanker

client = TestClient(app)


def test_resume_parser_metadata_extraction():
    text = (
        "Senior Staff Fullstack Engineer with 8 years of experience building high-scale products. "
        "Proficient in Python, FastAPI, React, TypeScript, PostgreSQL, Redis, Docker, and GraphQL. "
        "Architected distributed real-time sync systems handling millions of users."
    )
    meta = ResumeParser.extract_metadata(text)
    assert "Python" in meta["skills"] or "python" in [s.lower() for s in meta["skills"]]
    assert "FastAPI" in meta["skills"] or "fastapi" in [s.lower() for s in meta["skills"]]
    assert "PostgreSQL" in meta["skills"] or "postgresql" in [s.lower() for s in meta["skills"]]
    assert meta["experience_years"] == 8
    assert meta["seniority"] in ["senior", "staff"]


def test_multi_factor_ranker_3_day_constraint():
    profile = CandidateProfile(
        target_roles=["Senior Backend Engineer"],
        target_seniorities=["senior"],
        preferred_remote_types=["remote"],
        parsed_skills=["Python", "FastAPI", "PostgreSQL"],
        min_similarity_score=0.70,
        profile_embedding=[0.1] * 384,
    )
    
    # Job older than 3 days (e.g. 5 days ago)
    old_job = Job(
        title="Senior Backend Engineer",
        company="OldCo",
        seniority="senior",
        remote_type="remote",
        description="Looking for Python, FastAPI, PostgreSQL engineer",
        first_seen_at=datetime.now(timezone.utc) - timedelta(days=5),
        embedding=[0.1] * 384,
    )
    breakdown = MultiFactorRanker.score(profile, old_job)
    assert breakdown.final_score == 0.0
    assert "Failed hard criteria filter" in breakdown.reasons[0] or "older than 3 days" in breakdown.reasons[0]


def test_multi_factor_ranker_70_percent_high_alignment():
    profile = CandidateProfile(
        target_roles=["Fullstack Engineer"],
        target_seniorities=["senior"],
        preferred_remote_types=["remote"],
        parsed_skills=["React", "TypeScript", "Node.js", "PostgreSQL", "Redis"],
        min_similarity_score=0.70,
        profile_embedding=[0.05] * 384,
    )
    
    fresh_job = Job(
        title="Senior / Staff Fullstack Engineer",
        company="Linear",
        seniority="senior",
        remote_type="remote",
        description="We expect React, TypeScript, Node, PostgreSQL, and Redis experience.",
        first_seen_at=datetime.now(timezone.utc) - timedelta(hours=6),
        embedding=[0.05] * 384,
    )
    breakdown = MultiFactorRanker.score(profile, fresh_job)
    assert breakdown.final_score >= 0.70
    assert len(breakdown.matched_skills) > 0


def test_api_resume_upload_and_matches_flow():
    # 1. Register candidate
    email = f"test.flow.{datetime.now().timestamp()}@pulseai.dev"
    reg_resp = client.post("/api/users/", json={
        "email": email,
        "full_name": "Test Flow Candidate",
        "profile": {
            "target_roles": ["Fullstack Engineer"],
            "target_seniorities": ["senior"],
            "preferred_remote_types": ["remote"],
            "min_similarity_score": 0.70
        }
    })
    assert reg_resp.status_code == 201
    user_id = reg_resp.json()["id"]

    # 2. Upload resume plaintext
    resume_content = (
        "Senior Fullstack Engineer with 7 years of deep experience in React, TypeScript, "
        "Node.js, GraphQL, PostgreSQL, and Redis."
    )
    up_resp = client.post(f"/api/users/{user_id}/resume", data={"resume_text": resume_content})
    assert up_resp.status_code == 200
    data = up_resp.json()
    assert "React" in data["parsed_skills"]
    assert data["has_embedding"] is True

    # 3. Update profile with custom selected skills
    put_resp = client.put(f"/api/users/{user_id}/profile", json={
        "target_roles": ["Senior Fullstack Engineer", "Product Engineer"],
        "target_seniorities": ["senior"],
        "preferred_remote_types": ["remote"],
        "preferred_locations": ["Remote - US"],
        "raw_resume_text": resume_content,
        "parsed_skills": ["React", "TypeScript", "Node.js", "PostgreSQL", "Redis", "GraphQL"],
        "min_similarity_score": 0.70
    })
    assert put_resp.status_code == 200
    assert "GraphQL" in put_resp.json()["parsed_skills"]

    # 4. Fetch matches with min_score=0.70 and max_days=3
    match_resp = client.get(f"/api/users/{user_id}/matches?min_score=0.70&max_days=3")
    assert match_resp.status_code == 200
    matches = match_resp.json()
    # All returned matches must satisfy >= 0.70 score
    for m in matches:
        assert m["scores"]["final_score"] >= 0.70
