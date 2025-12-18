from pydantic import BaseModel
from typing import Optional
from datetime import date, datetime


class AuditBase(BaseModel):
    title: str
    description: Optional[str] = None
    audit_date: date


class AuditCreate(AuditBase):
    audit_type: str  # 'internal' or 'external'


class AuditUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    audit_date: Optional[date] = None


class AuditResponse(AuditBase):
    id: int
    audit_type: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AuditCountByDate(BaseModel):
    date: str
    internal: int
    external: int
    total: int


class YearlyStats(BaseModel):
    year: int
    total_audits: int
    internal_count: int
    external_count: int
