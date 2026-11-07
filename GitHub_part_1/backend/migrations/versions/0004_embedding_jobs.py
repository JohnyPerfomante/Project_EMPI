"""Persist precomputation requests for learning materials."""

import sqlalchemy as sa
from alembic import op

revision = "0004_embedding_jobs"
down_revision = "0003_indexes"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "embedding_jobs",
        sa.Column("text_digest", sa.String(64), primary_key=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("ready_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_embedding_jobs_ready_at", "embedding_jobs", ["ready_at"])


def downgrade():
    op.drop_table("embedding_jobs")
