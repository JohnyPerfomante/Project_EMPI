"""Index vector dimensions and common learning queries."""

from alembic import op

revision = "0003_indexes"
down_revision = "0002_schema"
branch_labels = None
depends_on = None


def upgrade():
    for dimension in (384, 768):
        op.execute(f"""
            CREATE INDEX ix_embeddings_hnsw_{dimension} ON embeddings
            USING hnsw ((embedding::vector({dimension})) vector_cosine_ops)
            WHERE vector_dims(embedding) = {dimension}
        """)
    op.execute("CREATE INDEX ix_analysis_latest ON analysis_results (submission_id, id DESC)")
    op.execute("CREATE INDEX ix_review_latest ON teacher_reviews (analysis_result_id, id DESC)")
    op.execute("CREATE INDEX ix_submissions_time ON submissions (created_at DESC)")
    op.execute("""
        ALTER TABLE courses ADD CONSTRAINT course_result_visibility
        CHECK (result_visibility IN ('automatic', 'reviewed', 'hidden'))
    """)


def downgrade():
    op.drop_constraint("course_result_visibility", "courses", type_="check")
    for index in (
        "ix_embeddings_hnsw_384",
        "ix_embeddings_hnsw_768",
        "ix_analysis_latest",
        "ix_review_latest",
        "ix_submissions_time",
    ):
        op.drop_index(index)
