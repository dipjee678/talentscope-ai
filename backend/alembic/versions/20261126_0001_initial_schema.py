"""Initial 14-table TalentScope AI schema.

Revision ID: 20261126_0001
Revises:
Create Date: 2026-11-26 02:45:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from app.core.database import Base
from app.models import entities  # noqa: F401

revision: str = "20261126_0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
