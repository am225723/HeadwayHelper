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
    op.add_column("users", sa.Column("full_name", sa.String(255), nullable=True))
    op.add_column("users", sa.Column("is_active", sa.Boolean(), server_default=sa.true()))
    op.add_column("output_documents", sa.Column("source_document_id", sa.String(36), sa.ForeignKey("source_documents.id"), nullable=True))
    op.add_column("output_documents", sa.Column("structured_data", sa.JSON(), nullable=True))
    op.create_table("reimbursement_rates", sa.Column("id", sa.String(36), primary_key=True), sa.Column("payer_name", sa.String(255), nullable=False), sa.Column("cpt_code", sa.String(20), nullable=False), sa.Column("amount", sa.Float(), nullable=False), sa.Column("is_active", sa.Boolean()), sa.Column("notes", sa.Text()), sa.Column("created_by", sa.String(255)), sa.Column("updated_by", sa.String(255)), sa.Column("created_at", sa.DateTime(timezone=True)), sa.Column("updated_at", sa.DateTime(timezone=True)))
    op.create_index("ix_reimbursement_rates_payer_cpt", "reimbursement_rates", ["payer_name", "cpt_code"])
    op.create_table("billing_rules", sa.Column("id", sa.String(36), primary_key=True), sa.Column("rule_key", sa.String(120), nullable=False, unique=True), sa.Column("rule_value_json", sa.JSON(), nullable=False), sa.Column("description", sa.Text()), sa.Column("version", sa.Integer()), sa.Column("created_at", sa.DateTime(timezone=True)), sa.Column("updated_at", sa.DateTime(timezone=True)), sa.Column("updated_by", sa.String(255)))
    op.create_table("service_types", sa.Column("id", sa.String(36), primary_key=True), sa.Column("name", sa.String(255), nullable=False, unique=True), sa.Column("is_active", sa.Boolean()), sa.Column("display_order", sa.Integer()), sa.Column("created_at", sa.DateTime(timezone=True)), sa.Column("updated_at", sa.DateTime(timezone=True)))
    op.create_table("classification_rules", sa.Column("id", sa.String(36), primary_key=True), sa.Column("category", sa.String(50), nullable=False), sa.Column("keyword_or_pattern", sa.String(255), nullable=False), sa.Column("is_active", sa.Boolean()), sa.Column("created_at", sa.DateTime(timezone=True)), sa.Column("updated_at", sa.DateTime(timezone=True)), sa.Column("updated_by", sa.String(255)))
    op.create_index("ix_classification_rules_category", "classification_rules", ["category"])
    op.create_table("app_settings", sa.Column("id", sa.String(36), primary_key=True), sa.Column("setting_key", sa.String(120), nullable=False, unique=True), sa.Column("setting_value_json", sa.JSON(), nullable=False), sa.Column("description", sa.Text()), sa.Column("version", sa.Integer()), sa.Column("created_at", sa.DateTime(timezone=True)), sa.Column("updated_at", sa.DateTime(timezone=True)), sa.Column("updated_by", sa.String(255)))
    op.create_table("document_templates", sa.Column("id", sa.String(36), primary_key=True), sa.Column("document_type", sa.String(50), nullable=False), sa.Column("template_name", sa.String(255), nullable=False), sa.Column("template_source", sa.Text(), nullable=False), sa.Column("placeholder_style", sa.String(50), nullable=False), sa.Column("cleanup_rules_json", sa.JSON(), nullable=False), sa.Column("is_active", sa.Boolean()), sa.Column("version", sa.Integer()), sa.Column("created_at", sa.DateTime(timezone=True)), sa.Column("updated_at", sa.DateTime(timezone=True)), sa.Column("updated_by", sa.String(255)))
    op.create_index("ix_document_templates_type_active", "document_templates", ["document_type", "is_active"])
    op.create_table(
        "template_render_logs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("document_type", sa.String(50), nullable=False),
        sa.Column("template_id", sa.String(36), sa.ForeignKey("document_templates.id")),
        sa.Column("patient_id", sa.String(36), sa.ForeignKey("patients.id", ondelete="SET NULL")),
        sa.Column("output_document_id", sa.String(36), sa.ForeignKey("output_documents.id", ondelete="SET NULL")),
        sa.Column("render_status", sa.String(50), nullable=False),
        sa.Column("missing_placeholders_json", sa.JSON()),
        sa.Column("unreplaced_placeholders_json", sa.JSON()),
        sa.Column("cleanup_warnings_json", sa.JSON()),
        sa.Column("render_context_snapshot_json", sa.JSON()),
        sa.Column("html_preview_snapshot", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_template_render_logs_document_type", "template_render_logs", ["document_type"])
    op.create_table(
        "config_change_log",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("config_type", sa.String(120), nullable=False),
        sa.Column("config_key", sa.String(255), nullable=False),
        sa.Column("previous_value_json", sa.JSON()),
        sa.Column("new_value_json", sa.JSON()),
        sa.Column("changed_by", sa.String(255)),
        sa.Column("changed_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_config_change_log_type_key", "config_change_log", ["config_type", "config_key"])
    op.create_table("auth_audit_log", sa.Column("id", sa.String(36), primary_key=True), sa.Column("email", sa.String(255), nullable=False), sa.Column("event_type", sa.String(80), nullable=False), sa.Column("success", sa.Boolean()), sa.Column("detail", sa.Text()), sa.Column("created_at", sa.DateTime(timezone=True)))
    op.create_index("ix_auth_audit_log_email", "auth_audit_log", ["email"])
    op.create_table("seed_runs", sa.Column("id", sa.String(36), primary_key=True), sa.Column("seed_key", sa.String(120), nullable=False), sa.Column("status", sa.String(50), nullable=False), sa.Column("detail_json", sa.JSON()), sa.Column("created_at", sa.DateTime(timezone=True)))
    op.create_index("ix_seed_runs_seed_key", "seed_runs", ["seed_key"])


def downgrade() -> None:
    for table in ["seed_runs", "auth_audit_log", "config_change_log", "template_render_logs", "document_templates", "app_settings", "classification_rules", "service_types", "billing_rules", "reimbursement_rates"]:
        op.drop_table(table)
    op.drop_column("users", "is_active")
    op.drop_column("users", "full_name")
    op.drop_column("output_documents", "structured_data")
    op.drop_column("output_documents", "source_document_id")
