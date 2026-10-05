"""add face.person_id for per-face clustering

Revision ID: 1c7c4ca831da
Revises: 8721b3741ca6
Create Date: 2026-09-13 02:23:08.032926

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1c7c4ca831da'
down_revision: Union[str, None] = '8721b3741ca6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # NOTE: autogenerate wanted to drop ix_face_embeddings_embedding_cosine
    # and ix_photo_embeddings_embedding_cosine here -- those are the real
    # HNSW indexes from the baseline migration, created via raw SQL because
    # Alembic's autogenerate doesn't recognize hand-written `op.execute`
    # index creation. Removed those two lines; only the real schema change
    # (faces.person_id) remains.
    op.add_column('faces', sa.Column('person_id', sa.UUID(), nullable=True))
    op.create_index(op.f('ix_faces_person_id'), 'faces', ['person_id'], unique=False)
    op.create_foreign_key(None, 'faces', 'people', ['person_id'], ['id'])


def downgrade() -> None:
    op.drop_constraint(None, 'faces', type_='foreignkey')
    op.drop_index(op.f('ix_faces_person_id'), table_name='faces')
    op.drop_column('faces', 'person_id')
