from datetime import date, datetime, timezone
from enum import StrEnum
from uuid import uuid4

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Index, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def new_id() -> str:
    return str(uuid4())


class FileType(StrEnum):
    INTAKE = "INTAKE"
    ASSESSMENT = "ASSESSMENT"
    ZOOM_NOTE = "ZOOM_NOTE"
    UNKNOWN = "UNKNOWN"


class DocumentType(StrEnum):
    SUMMARY = "SUMMARY"
    SESSION_NOTE = "SESSION_NOTE"
    TREATMENT_PLAN = "TREATMENT_PLAN"


class OutputStatus(StrEnum):
    DRAFT = "DRAFT"
    FINAL = "FINAL"
    ERROR = "ERROR"


class Role(StrEnum):
    ADMIN = "ADMIN"
    PROVIDER = "PROVIDER"


class ReviewStatusValue(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class Patient(Base):
    __tablename__ = "patients"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    drive_folder_id: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)

    source_documents: Mapped[list["SourceDocument"]] = relationship(back_populates="patient", cascade="all, delete-orphan")
    output_documents: Mapped[list["OutputDocument"]] = relationship(back_populates="patient", cascade="all, delete-orphan")
    processing_runs: Mapped[list["ProcessingRun"]] = relationship(back_populates="patient", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"Patient(id={self.id!r}, name={self.name!r})"


class SourceDocument(Base):
    __tablename__ = "source_documents"
    __table_args__ = (Index("ix_source_documents_file_type", "file_type"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id", ondelete="CASCADE"), nullable=False)
    drive_file_id: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_type: Mapped[str] = mapped_column(String(50), nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    processed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

    patient: Mapped[Patient] = relationship(back_populates="source_documents")
    processed_file: Mapped["ProcessedFile"] = relationship(back_populates="source_document", cascade="all, delete-orphan")


class OutputDocument(Base):
    __tablename__ = "output_documents"
    __table_args__ = (Index("ix_output_documents_doc_type", "doc_type"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id", ondelete="CASCADE"), nullable=False)
    doc_type: Mapped[str] = mapped_column(String(50), nullable=False)
    drive_file_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    summary_id: Mapped[str | None] = mapped_column(ForeignKey("output_documents.id"), nullable=True)
    session_note_id: Mapped[str | None] = mapped_column(ForeignKey("output_documents.id"), nullable=True)
    source_document_id: Mapped[str | None] = mapped_column(ForeignKey("source_documents.id"), nullable=True)
    content: Mapped[str] = mapped_column(Text, default="")
    structured_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    status: Mapped[str] = mapped_column(String(50), default=OutputStatus.DRAFT)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    patient: Mapped[Patient] = relationship(back_populates="output_documents")
    billing_summary: Mapped["BillingSummary"] = relationship(back_populates="output_document", cascade="all, delete-orphan")
    review_statuses: Mapped[list["ReviewStatus"]] = relationship(back_populates="output_document", cascade="all, delete-orphan")


class ProcessedFile(Base):
    __tablename__ = "processed_files"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    source_document_id: Mapped[str] = mapped_column(ForeignKey("source_documents.id", ondelete="CASCADE"), nullable=False)
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

    source_document: Mapped[SourceDocument] = relationship(back_populates="processed_file")


class BillingSummary(Base):
    __tablename__ = "billing_summaries"
    __table_args__ = (Index("ix_billing_summaries_date_of_service", "date_of_service"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    output_document_id: Mapped[str] = mapped_column(ForeignKey("output_documents.id", ondelete="CASCADE"), nullable=False)
    patient_name: Mapped[str] = mapped_column(String(255), nullable=False)
    date_of_service: Mapped[date] = mapped_column(Date, nullable=False)
    service_name: Mapped[str] = mapped_column(String(255), nullable=False)
    icd10_codes: Mapped[str] = mapped_column(String(255), nullable=False)
    cpt_codes: Mapped[str] = mapped_column(String(255), nullable=False)
    psychotherapy_minutes: Mapped[int] = mapped_column(Integer, default=0)
    headway_block: Mapped[str] = mapped_column(Text, nullable=False)
    reimbursement_notes: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

    output_document: Mapped[OutputDocument] = relationship(back_populates="billing_summary")


class ProcessingRun(Base):
    __tablename__ = "processing_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id", ondelete="CASCADE"), nullable=False)
    doc_type: Mapped[str] = mapped_column(String(50), nullable=False)
    run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    success: Mapped[bool] = mapped_column(Boolean, default=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    patient: Mapped[Patient] = relationship(back_populates="processing_runs")


class User(Base):
    __tablename__ = "users"
    __table_args__ = (Index("ix_users_email", "email", unique=True),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)

    reviews: Mapped[list["ReviewStatus"]] = relationship(back_populates="reviewer")


class ReviewStatus(Base):
    __tablename__ = "review_statuses"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    output_document_id: Mapped[str] = mapped_column(ForeignKey("output_documents.id", ondelete="CASCADE"), nullable=False)
    reviewer_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    comments: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)

    output_document: Mapped[OutputDocument] = relationship(back_populates="review_statuses")
    reviewer: Mapped[User] = relationship(back_populates="reviews")


class ReimbursementRate(Base):
    __tablename__ = "reimbursement_rates"
    __table_args__ = (Index("ix_reimbursement_rates_payer_cpt", "payer_name", "cpt_code"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    payer_name: Mapped[str] = mapped_column(String(255), nullable=False)
    cpt_code: Mapped[str] = mapped_column(String(20), nullable=False)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)


class BillingRule(Base):
    __tablename__ = "billing_rules"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    rule_key: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    rule_value_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)


class ServiceType(Base):
    __tablename__ = "service_types"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    display_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)


class ClassificationRule(Base):
    __tablename__ = "classification_rules"
    __table_args__ = (Index("ix_classification_rules_category", "category"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    keyword_or_pattern: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)


class AppSetting(Base):
    __tablename__ = "app_settings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    setting_key: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    setting_value_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)


class DocumentTemplate(Base):
    __tablename__ = "document_templates"
    __table_args__ = (Index("ix_document_templates_type_active", "document_type", "is_active"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    document_type: Mapped[str] = mapped_column(String(50), nullable=False)
    template_name: Mapped[str] = mapped_column(String(255), nullable=False)
    template_source: Mapped[str] = mapped_column(Text, nullable=False)
    placeholder_style: Mapped[str] = mapped_column(String(50), nullable=False)
    cleanup_rules_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)
