from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core.logging import logger
from src.modules.users.models import User, CandidateProfile
from src.modules.users.schemas import ProfileCreateOrUpdate
from src.modules.users.resume_parser import ResumeParser
from src.modules.embeddings.service import get_embedding_provider
from src.modules.embeddings.base import BaseEmbeddingProvider


class UserRepository:
    """Handles User creation, profile updates, and automatic profile vector embedding."""

    @staticmethod
    def get_by_id(db: Session, user_id: str) -> Optional[User]:
        return db.get(User, user_id)

    @staticmethod
    def get_by_email(db: Session, email: str) -> Optional[User]:
        stmt = select(User).where(User.email == email)
        return db.execute(stmt).scalars().first()

    @classmethod
    def create_user(
        cls,
        db: Session,
        email: str,
        telegram_chat_id: Optional[str] = None,
        full_name: Optional[str] = None,
        alert_frequency: str = "daily_9am",
        timezone_str: str = "UTC",
        initial_profile: Optional[ProfileCreateOrUpdate] = None,
    ) -> User:
        user = User(
            email=email,
            telegram_chat_id=telegram_chat_id,
            full_name=full_name,
            alert_frequency=alert_frequency,
            timezone=timezone_str,
        )
        db.add(user)
        db.flush()

        profile = CandidateProfile(
            user_id=user.id,
            target_roles=initial_profile.target_roles if initial_profile else [],
            target_seniorities=initial_profile.target_seniorities if initial_profile else [],
            preferred_remote_types=initial_profile.preferred_remote_types if initial_profile else [],
            preferred_locations=initial_profile.preferred_locations if initial_profile else [],
            raw_resume_text=initial_profile.raw_resume_text if initial_profile else None,
            min_similarity_score=initial_profile.min_similarity_score if initial_profile else 0.65,
        )
        db.add(profile)
        db.flush()

        if initial_profile and (initial_profile.target_roles or initial_profile.raw_resume_text):
            cls.update_profile(db, user.id, initial_profile)

        db.commit()
        db.refresh(user)
        return user

    @classmethod
    def update_profile(
        cls,
        db: Session,
        user_id: str,
        profile_data: ProfileCreateOrUpdate,
        embedding_provider: Optional[BaseEmbeddingProvider] = None,
    ) -> CandidateProfile:
        stmt = select(CandidateProfile).where(CandidateProfile.user_id == user_id)
        profile = db.execute(stmt).scalars().first()

        if profile is None:
            profile = CandidateProfile(user_id=user_id)
            db.add(profile)
            db.flush()

        # Update search preferences
        profile.target_roles = profile_data.target_roles
        profile.target_seniorities = profile_data.target_seniorities
        profile.preferred_remote_types = profile_data.preferred_remote_types
        profile.preferred_locations = profile_data.preferred_locations
        profile.min_similarity_score = profile_data.min_similarity_score

        if profile_data.raw_resume_text is not None:
            profile.raw_resume_text = profile_data.raw_resume_text

        if profile_data.parsed_skills is not None:
            profile.parsed_skills = profile_data.parsed_skills
        elif profile_data.raw_resume_text is not None:
            # Extract skills automatically from resume
            extracted_skills = ResumeParser.extract_skills(profile_data.raw_resume_text)
            profile.parsed_skills = extracted_skills

        # Generate profile vector embedding
        profile_text = ResumeParser.format_profile_for_embedding(
            target_roles=profile.target_roles or [],
            target_seniorities=profile.target_seniorities or [],
            preferred_remote_types=profile.preferred_remote_types or [],
            skills=profile.parsed_skills or [],
            resume_text=profile.raw_resume_text,
        )

        provider = embedding_provider or get_embedding_provider()
        vectors = provider.embed_texts([profile_text])
        if vectors:
            profile.profile_embedding = vectors[0]
            profile.embedded_at = datetime.now(timezone.utc)

        db.commit()
        db.refresh(profile)
        logger.info(
            "Updated and embedded candidate profile",
            user_id=user_id,
            skills_count=len(profile.parsed_skills),
            roles=profile.target_roles,
        )
        return profile
