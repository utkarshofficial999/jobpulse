from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core.database import get_db
from src.modules.users.models import User, CandidateProfile
from src.modules.users.schemas import UserCreate, UserRead, ProfileCreateOrUpdate, ProfileRead, ResumeUploadResponse
from src.modules.users.repository import UserRepository
from src.modules.users.resume_parser import ResumeParser
from src.modules.matching.engine import MatchingEngine
from src.modules.notifications.models import NotificationOutbox
from src.modules.notifications.outbox import OutboxService

router = APIRouter(prefix="/users", tags=["Users & Matching"])


@router.post("/", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register_user(payload: UserCreate, db: Session = Depends(get_db)):
    """Registers a candidate with their target role, seniority, and preferences."""
    existing = UserRepository.get_by_email(db, payload.email)
    if existing:
        raise HTTPException(status_code=400, detail="User with this email already exists")

    if payload.telegram_chat_id:
        existing_tg = db.query(User).filter(User.telegram_chat_id == payload.telegram_chat_id).first()
        if existing_tg:
            raise HTTPException(status_code=400, detail="User with this telegram_chat_id already exists")

    user = UserRepository.create_user(
        db=db,
        email=payload.email,
        telegram_chat_id=payload.telegram_chat_id,
        full_name=payload.full_name,
        alert_frequency=payload.alert_frequency,
        timezone_str=payload.timezone,
        initial_profile=payload.profile,
    )
    return user


@router.get("/{user_id}", response_model=UserRead)
def get_user(user_id: str, db: Session = Depends(get_db)):
    """Retrieves candidate profile and preferences."""
    user = UserRepository.get_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.put("/{user_id}/profile", response_model=ProfileRead)
def update_user_profile(
    user_id: str,
    payload: ProfileCreateOrUpdate,
    db: Session = Depends(get_db),
):
    """Updates candidate targeting preferences, selected skills, and re-embeds the profile."""
    user = UserRepository.get_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    updated = UserRepository.update_profile(db, user_id, payload)
    return ProfileRead(
        id=updated.id,
        target_roles=updated.target_roles or [],
        target_seniorities=updated.target_seniorities or [],
        preferred_remote_types=updated.preferred_remote_types or [],
        preferred_locations=updated.preferred_locations or [],
        parsed_skills=updated.parsed_skills or [],
        raw_resume_text=updated.raw_resume_text,
        min_similarity_score=updated.min_similarity_score,
        has_embedding=updated.profile_embedding is not None,
        created_at=updated.created_at,
        updated_at=updated.updated_at,
    )


@router.post("/{user_id}/resume", response_model=ResumeUploadResponse)
async def upload_resume(
    user_id: str,
    file: Optional[UploadFile] = File(None),
    resume_text: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    """
    Uploads candidate resume (as PDF, DOCX, or plaintext).
    Automatically extracts technical skills, years of experience, and embeds the profile vector for matching.
    """
    user = UserRepository.get_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    extracted_text = ""
    if file and file.filename:
        content = await file.read()
        extracted_text = ResumeParser.extract_text(file.filename, content)
    elif resume_text:
        extracted_text = resume_text
    else:
        raise HTTPException(status_code=400, detail="Either file (PDF/DOCX/TXT) or resume_text must be provided")

    metadata = ResumeParser.extract_metadata(extracted_text)

    # Blend current target roles with extracted if candidate had none
    curr_roles = user.profile.target_roles if (user.profile and user.profile.target_roles) else metadata.get("target_roles", [])
    curr_seniorities = user.profile.target_seniorities if (user.profile and user.profile.target_seniorities) else [metadata.get("seniority", "senior")]

    profile_update = ProfileCreateOrUpdate(
        target_roles=curr_roles,
        target_seniorities=curr_seniorities,
        preferred_remote_types=user.profile.preferred_remote_types if user.profile else ["remote"],
        preferred_locations=user.profile.preferred_locations if user.profile else ["Remote - US"],
        raw_resume_text=extracted_text,
        parsed_skills=metadata.get("skills", []),
        min_similarity_score=user.profile.min_similarity_score if user.profile else 0.70,
    )

    updated_profile = UserRepository.update_profile(db, user_id, profile_update)
    return ResumeUploadResponse(
        id=updated_profile.id,
        target_roles=updated_profile.target_roles or [],
        target_seniorities=updated_profile.target_seniorities or [],
        preferred_remote_types=updated_profile.preferred_remote_types or [],
        preferred_locations=updated_profile.preferred_locations or [],
        parsed_skills=updated_profile.parsed_skills or [],
        raw_resume_text=updated_profile.raw_resume_text,
        summary=metadata.get("summary"),
        experience_years=metadata.get("experience_years"),
        seniority=metadata.get("seniority"),
        min_similarity_score=updated_profile.min_similarity_score,
        has_embedding=updated_profile.profile_embedding is not None,
    )


@router.get("/{user_id}/matches")
def get_user_matches(
    user_id: str,
    limit: int = Query(10, ge=1, le=50),
    min_score: Optional[float] = Query(0.70, ge=0.0, le=1.0),
    max_days: Optional[int] = Query(3, ge=1, le=30),
    db: Session = Depends(get_db),
):
    """
    Runs the reverse matching engine to find active jobs tailored to this candidate profile.
    Ranks by semantic vector alignment, selected skills overlap, title keyword match, and 3-day recency.
    Enforces min_score (70% match) and max_days (at max 3 days older).
    """
    matches = MatchingEngine.match_candidate(
        db, user_id, limit=limit, min_score=min_score, max_days=max_days
    )
    return [
        {
            "job_id": m.job.id,
            "title": m.job.title,
            "company": m.job.company,
            "seniority": m.job.seniority,
            "remote_type": m.job.remote_type,
            "locations": m.job.locations,
            "apply_url": m.job.apply_url,
            "first_seen_at": m.job.first_seen_at,
            "scores": {
                "final_score": m.breakdown.final_score,
                "vector_similarity": m.breakdown.vector_score,
                "skill_score": m.breakdown.skill_score,
                "title_keyword_score": m.breakdown.title_score,
                "recency_score": m.breakdown.recency_score,
            },
            "matched_skills": m.breakdown.matched_skills,
            "reasons": m.breakdown.reasons,
        }
        for m in matches
    ]


@router.post("/{user_id}/feedback")
def record_feedback(
    user_id: str,
    job_id: str = Query(...),
    action: str = Query(..., description="Action: 'applied', 'saved', 'dismissed', 'viewed'"),
    db: Session = Depends(get_db),
):
    """Records user action on a job to refine recommendations."""
    if action not in ["applied", "saved", "dismissed", "viewed"]:
        raise HTTPException(status_code=400, detail="Invalid action")
    feedback = MatchingEngine.record_feedback(db, user_id, job_id, action)
    return {"status": "success", "feedback_id": feedback.id, "action": feedback.action}


@router.post("/{user_id}/trigger-digest")
def trigger_user_digest(user_id: str, db: Session = Depends(get_db)):
    """Triggers an on-demand match and queues an alert in the outbox."""
    user = UserRepository.get_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    matches = MatchingEngine.match_candidate(db, user_id, limit=5)
    if not matches:
        return {"status": "no_matches", "message": "No new matching opportunities found at this time"}

    cards = [
        {
            "job_id": m.job.id,
            "title": m.job.title,
            "company": m.job.company,
            "locations": m.job.locations,
            "remote_type": m.job.remote_type,
            "apply_url": m.job.apply_url,
            "match_score": m.breakdown.final_score,
            "matched_skills": m.breakdown.matched_skills,
        }
        for m in matches
    ]
    payload = {
        "user_name": user.full_name or "Candidate",
        "matches": cards,
    }

    channel = "telegram" if user.telegram_chat_id else "email"
    recipient = user.telegram_chat_id if user.telegram_chat_id else user.email

    outbox_item = OutboxService.queue_notification(
        db=db,
        user_id=user.id,
        channel=channel,
        recipient=recipient,
        subject="Pulse AI: Your Job Matches",
        payload=payload,
    )
    db.commit()

    # Automatically dispatch outbox item
    OutboxService.drain_outbox(db)

    return {
        "status": "success",
        "outbox_id": outbox_item.id,
        "channel": channel,
        "recipient": recipient,
        "matches_count": len(cards),
    }
