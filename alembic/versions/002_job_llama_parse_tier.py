"""Add optional per-job LlamaCloud parse tier."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "002_job_llama_parse_tier"
down_revision: Union[str, None] = "001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "ingestion_jobs",
        sa.Column("llama_parse_tier", sa.String(32), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("ingestion_jobs", "llama_parse_tier")
