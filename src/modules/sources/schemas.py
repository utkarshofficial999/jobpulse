from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel, Field


class SourceCreate(BaseModel):
    name: str = Field(..., example="Stripe Greenhouse")
    connector_type: str = Field("greenhouse", example="greenhouse")
    config: dict[str, Any] = Field(..., example={"board_token": "stripe"})
    poll_interval_seconds: int = Field(3600, ge=60, example=3600)


class SourceRead(BaseModel):
    id: str
    name: str
    connector_type: str
    config: dict[str, Any]
    is_active: bool
    poll_interval_seconds: int
    next_run_at: datetime
    last_run_at: Optional[datetime] = None
    consecutive_failures: int
    last_error: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
