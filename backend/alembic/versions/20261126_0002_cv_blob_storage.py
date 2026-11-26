"""Add encrypted_file_blob column to uploaded_cvs for database-backed CV storage.

Revision ID: 20261126_0002
Revises: 20261126_0001
Create Date: 2026-11-26 18:00:00
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261126_0002"
down_revision: Union[str, None] = "20261126_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(table: str, column: str) -> bool:
    insp = sa.inspect(op.get_bind())
    return any(c["name"] == column for c in insp.get_columns(table))


def upgrade() -> None:
    # 0001 builds tables from current metadata, so fresh databases already have the column.
    if not _has_column("uploaded_cvs", "encrypted_file_blob"):
        op.add_column("uploaded_cvs", sa.Column("encrypted_file_blob", sa.LargeBinary(), nullable=True))


def downgrade() -> None:
    if _has_column("uploaded_cvs", "encrypted_file_blob"):
        with op.batch_alter_table("uploaded_cvs") as batch:
            batch.drop_column("encrypted_file_blob")
