from alembic import context

from app.database.session import engine
from app.models import Base


def include_object(obj, name, kind, reflected, compare_to):
    # Dimension-specific expression indexes are maintained in migration 0003.
    return not (kind == "index" and name.startswith("ix_embeddings_hnsw_"))


with engine().connect() as connection:
    context.configure(
        connection=connection, target_metadata=Base.metadata, compare_type=True, include_object=include_object
    )
    with context.begin_transaction():
        context.run_migrations()
