from __future__ import annotations
from typing import Optional, Union, List, Any
from pydantic import BaseModel, Field, field_validator
from enum import Enum
from datetime import datetime


class DocumentType(str, Enum):
    DIVIDEND = "DIVIDEND"
    SPLIT = "SPLIT"
    BONUS = "BONUS"
    RIGHTS = "RIGHTS"
    CAPITAL_RETURN = "CAPITAL_RETURN"


class FieldEvidence(BaseModel):
    page: int
    snippet: str


class KPIField(BaseModel):
    value: Optional[Union[str, float, int]] = None
    evidence: Optional[Union[FieldEvidence, List[FieldEvidence]]] = None
    confidence: float = 0.0


class ExtractionResult(BaseModel):
    doc_id: Optional[str] = None
    document_type: Optional[DocumentType] = None
    company_name: KPIField = Field(default_factory=KPIField)
    ticker: KPIField = Field(default_factory=KPIField)
    isin: KPIField = Field(default_factory=KPIField)
    ex_date: KPIField = Field(default_factory=KPIField)
    record_date: KPIField = Field(default_factory=KPIField)
    payment_date: KPIField = Field(default_factory=KPIField)
    dividend_per_share: KPIField = Field(default_factory=KPIField)
    currency: KPIField = Field(default_factory=KPIField)
    franking_percentage: KPIField = Field(default_factory=KPIField)
    ratio: KPIField = Field(default_factory=KPIField)
    announcement_date: KPIField = Field(default_factory=KPIField)
    overall_confidence: float = 0.0
    warnings: List[str] = []

    @field_validator("overall_confidence")
    @classmethod
    def clamp_confidence(cls, v):
        return max(0.0, min(1.0, v))


class RawExtraction(BaseModel):
    doc_id: str
    text_by_page: dict = {}
    tables_by_page: dict = {}
    ocr_used_pages: List[int] = []
    extraction_timestamp: str
