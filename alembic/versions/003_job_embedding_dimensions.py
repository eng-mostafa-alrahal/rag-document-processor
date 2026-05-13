"""Add optional per-job embedding output dimension (Matryoshka / OpenAI dimensions)."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "003_job_embedding_dimensions"
down_revision: Union[str, None] = "002_job_llama_parse_tier"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "ingestion_jobs",
        sa.Column("embedding_dimensions", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("ingestion_jobs", "embedding_dimensions")
