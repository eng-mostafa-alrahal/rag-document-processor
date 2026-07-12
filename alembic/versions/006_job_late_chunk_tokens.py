"""Per-job late-chunking token controls (min/max tokens per merged chunk)."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "006_job_late_chunk_tokens"
down_revision: Union[str, None] = "005_api_keys_drop_users"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("ingestion_jobs", sa.Column("late_chunk_min_tokens", sa.Integer(), nullable=True))
    op.add_column("ingestion_jobs", sa.Column("late_chunk_max_tokens", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("ingestion_jobs", "late_chunk_max_tokens")
    op.drop_column("ingestion_jobs", "late_chunk_min_tokens")
