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


def downgrade() -> None:
    op.drop_column("output_documents", "structured_data")
    op.drop_column("output_documents", "source_document_id")
