"""initial schema

Revision ID: 20260425_0001
Revises:
Create Date: 2026-04-25
"""
from alembic import op
import sqlalchemy as sa

revision = "20260425_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("patients", sa.Column("id", sa.String(36), primary_key=True), sa.Column("name", sa.String(255), nullable=False), sa.Column("drive_folder_id", sa.String(255), nullable=False, unique=True), sa.Column("created_at", sa.DateTime(timezone=True)), sa.Column("updated_at", sa.DateTime(timezone=True)))
    op.create_table("users", sa.Column("id", sa.String(36), primary_key=True), sa.Column("email", sa.String(255), nullable=False, unique=True), sa.Column("password_hash", sa.String(255), nullable=False), sa.Column("role", sa.String(50), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True)), sa.Column("updated_at", sa.DateTime(timezone=True)))
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_table("source_documents", sa.Column("id", sa.String(36), primary_key=True), sa.Column("patient_id", sa.String(36), sa.ForeignKey("patients.id", ondelete="CASCADE"), nullable=False), sa.Column("drive_file_id", sa.String(255), nullable=False, unique=True), sa.Column("name", sa.String(255), nullable=False), sa.Column("file_type", sa.String(50), nullable=False), sa.Column("uploaded_at", sa.DateTime(timezone=True)), sa.Column("processed", sa.Boolean(), default=False), sa.Column("created_at", sa.DateTime(timezone=True)))
    op.create_index("ix_source_documents_file_type", "source_documents", ["file_type"])
    op.create_table("output_documents", sa.Column("id", sa.String(36), primary_key=True), sa.Column("patient_id", sa.String(36), sa.ForeignKey("patients.id", ondelete="CASCADE"), nullable=False), sa.Column("doc_type", sa.String(50), nullable=False), sa.Column("drive_file_id", sa.String(255)), sa.Column("summary_id", sa.String(36), sa.ForeignKey("output_documents.id")), sa.Column("session_note_id", sa.String(36), sa.ForeignKey("output_documents.id")), sa.Column("source_document_id", sa.String(36), sa.ForeignKey("source_documents.id")), sa.Column("content", sa.Text()), sa.Column("structured_data", sa.JSON()), sa.Column("created_at", sa.DateTime(timezone=True)), sa.Column("status", sa.String(50)), sa.Column("error_message", sa.Text()))
    op.create_index("ix_output_documents_doc_type", "output_documents", ["doc_type"])
    op.create_table("processed_files", sa.Column("id", sa.String(36), primary_key=True), sa.Column("source_document_id", sa.String(36), sa.ForeignKey("source_documents.id", ondelete="CASCADE"), nullable=False), sa.Column("processed_at", sa.DateTime(timezone=True)))
    op.create_table("billing_summaries", sa.Column("id", sa.String(36), primary_key=True), sa.Column("output_document_id", sa.String(36), sa.ForeignKey("output_documents.id", ondelete="CASCADE"), nullable=False), sa.Column("patient_name", sa.String(255), nullable=False), sa.Column("date_of_service", sa.Date(), nullable=False), sa.Column("service_name", sa.String(255), nullable=False), sa.Column("icd10_codes", sa.String(255), nullable=False), sa.Column("cpt_codes", sa.String(255), nullable=False), sa.Column("psychotherapy_minutes", sa.Integer()), sa.Column("headway_block", sa.Text(), nullable=False), sa.Column("reimbursement_notes", sa.JSON()), sa.Column("created_at", sa.DateTime(timezone=True)))
    op.create_index("ix_billing_summaries_date_of_service", "billing_summaries", ["date_of_service"])
    op.create_table("processing_runs", sa.Column("id", sa.String(36), primary_key=True), sa.Column("patient_id", sa.String(36), sa.ForeignKey("patients.id", ondelete="CASCADE"), nullable=False), sa.Column("doc_type", sa.String(50), nullable=False), sa.Column("run_at", sa.DateTime(timezone=True)), sa.Column("success", sa.Boolean()), sa.Column("error_message", sa.Text()))
    op.create_table("review_statuses", sa.Column("id", sa.String(36), primary_key=True), sa.Column("output_document_id", sa.String(36), sa.ForeignKey("output_documents.id", ondelete="CASCADE"), nullable=False), sa.Column("reviewer_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False), sa.Column("status", sa.String(50), nullable=False), sa.Column("comments", sa.Text()), sa.Column("updated_at", sa.DateTime(timezone=True)))


def downgrade() -> None:
    for table in ["review_statuses", "processing_runs", "billing_summaries", "processed_files", "output_documents", "source_documents", "users", "patients"]:
        op.drop_table(table)
