"""generation metadata

Revision ID: 20260425_0002
Revises: 20260425_0001
Create Date: 2026-04-25
"""
from alembic import op
import sqlalchemy as sa

revision = "20260425_0002"
down_revision = "20260425_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("output_documents", sa.Column("source_document_id", sa.String(36), sa.ForeignKey("source_documents.id"), nullable=True))
    op.add_column("output_documents", sa.Column("structured_data", sa.JSON(), nullable=True))
    op.create_table("reimbursement_rates", sa.Column("id", sa.String(36), primary_key=True), sa.Column("payer_name", sa.String(255), nullable=False), sa.Column("cpt_code", sa.String(20), nullable=False), sa.Column("amount", sa.Float(), nullable=False), sa.Column("is_active", sa.Boolean()), sa.Column("notes", sa.Text()), sa.Column("created_at", sa.DateTime(timezone=True)), sa.Column("updated_at", sa.DateTime(timezone=True)))
    op.create_index("ix_reimbursement_rates_payer_cpt", "reimbursement_rates", ["payer_name", "cpt_code"])
    op.create_table("billing_rules", sa.Column("id", sa.String(36), primary_key=True), sa.Column("rule_key", sa.String(120), nullable=False, unique=True), sa.Column("rule_value_json", sa.JSON(), nullable=False), sa.Column("description", sa.Text()), sa.Column("updated_at", sa.DateTime(timezone=True)))
    op.create_table("service_types", sa.Column("id", sa.String(36), primary_key=True), sa.Column("name", sa.String(255), nullable=False, unique=True), sa.Column("is_active", sa.Boolean()), sa.Column("display_order", sa.Integer()), sa.Column("created_at", sa.DateTime(timezone=True)), sa.Column("updated_at", sa.DateTime(timezone=True)))
    op.create_table("classification_rules", sa.Column("id", sa.String(36), primary_key=True), sa.Column("category", sa.String(50), nullable=False), sa.Column("keyword_or_pattern", sa.String(255), nullable=False), sa.Column("is_active", sa.Boolean()), sa.Column("created_at", sa.DateTime(timezone=True)), sa.Column("updated_at", sa.DateTime(timezone=True)))
    op.create_index("ix_classification_rules_category", "classification_rules", ["category"])
    op.create_table("app_settings", sa.Column("id", sa.String(36), primary_key=True), sa.Column("setting_key", sa.String(120), nullable=False, unique=True), sa.Column("setting_value_json", sa.JSON(), nullable=False), sa.Column("description", sa.Text()), sa.Column("updated_at", sa.DateTime(timezone=True)))
    op.create_table("document_templates", sa.Column("id", sa.String(36), primary_key=True), sa.Column("document_type", sa.String(50), nullable=False), sa.Column("template_name", sa.String(255), nullable=False), sa.Column("template_source", sa.Text(), nullable=False), sa.Column("placeholder_style", sa.String(50), nullable=False), sa.Column("cleanup_rules_json", sa.JSON(), nullable=False), sa.Column("is_active", sa.Boolean()), sa.Column("created_at", sa.DateTime(timezone=True)), sa.Column("updated_at", sa.DateTime(timezone=True)))
    op.create_index("ix_document_templates_type_active", "document_templates", ["document_type", "is_active"])


def downgrade() -> None:
    for table in ["document_templates", "app_settings", "classification_rules", "service_types", "billing_rules", "reimbursement_rates"]:
        op.drop_table(table)
    op.drop_column("output_documents", "structured_data")
    op.drop_column("output_documents", "source_document_id")
