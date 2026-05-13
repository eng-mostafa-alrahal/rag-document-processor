"""Per-job embedding pipeline, macro splitter, embedder provider, and model overrides."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "004_job_embed_controls"
down_revision: Union[str, None] = "003_job_embedding_dimensions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("ingestion_jobs", sa.Column("embedding_pipeline", sa.String(length=32), nullable=True))
    op.add_column("ingestion_jobs", sa.Column("macro_splitter", sa.String(length=32), nullable=True))
    op.add_column("ingestion_jobs", sa.Column("embedder_provider", sa.String(length=16), nullable=True))
    op.add_column("ingestion_jobs", sa.Column("openai_embedding_model", sa.String(length=128), nullable=True))
    op.add_column("ingestion_jobs", sa.Column("jina_embedding_model", sa.String(length=128), nullable=True))


def downgrade() -> None:
    op.drop_column("ingestion_jobs", "jina_embedding_model")
    op.drop_column("ingestion_jobs", "openai_embedding_model")
    op.drop_column("ingestion_jobs", "embedder_provider")
    op.drop_column("ingestion_jobs", "macro_splitter")
    op.drop_column("ingestion_jobs", "embedding_pipeline")
