from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel, EmailStr, Field, ConfigDict


class ProfileCreateOrUpdate(BaseModel):
    target_roles: list[str] = Field(default_factory=list, json_schema_extra={"example": ["Backend Engineer", "Platform Engineer"]})
    target_seniorities: list[str] = Field(default_factory=list, json_schema_extra={"example": ["mid", "senior"]})
    preferred_remote_types: list[str] = Field(default_factory=list, json_schema_extra={"example": ["remote", "hybrid"]})
    preferred_locations: list[str] = Field(default_factory=list, json_schema_extra={"example": ["United States", "Remote"]})
    raw_resume_text: Optional[str] = Field(None, json_schema_extra={"example": "Experienced Python & Go engineer with 5 years building high-scale distributed systems with PostgreSQL and Redis."})
    min_similarity_score: float = Field(0.65, ge=0.0, le=1.0)


class UserCreate(BaseModel):
    email: EmailStr = Field(...)
    telegram_chat_id: Optional[str] = Field(None, json_schema_extra={"example": "123456789"})
    full_name: Optional[str] = Field(None, json_schema_extra={"example": "Alex Developer"})
    alert_frequency: str = Field("daily_9am", json_schema_extra={"example": "daily_9am"})
    timezone: str = Field("UTC", json_schema_extra={"example": "UTC"})
    profile: Optional[ProfileCreateOrUpdate] = None


class ProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    target_roles: list[str]
    target_seniorities: list[str]
    preferred_remote_types: list[str]
    preferred_locations: list[str]
    parsed_skills: list[str]
    min_similarity_score: float
    has_embedding: bool = False
    created_at: datetime
    updated_at: datetime


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    telegram_chat_id: Optional[str] = None
    full_name: Optional[str] = None
    is_active: bool
    alert_frequency: str
    timezone: str
    created_at: datetime
    profile: Optional[ProfileRead] = None
