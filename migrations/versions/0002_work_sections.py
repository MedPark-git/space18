"""separate GMP and GTP work sections"""
from alembic import op
import sqlalchemy as sa
revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None
def upgrade():
    op.add_column("document", sa.Column("section", sa.String(50), nullable=True))
    op.execute("UPDATE document SET section = 'records' WHERE section IS NULL")
    op.alter_column("document", "section", nullable=False)
    op.create_index("ix_document_section", "document", ["section"])
    op.drop_constraint("uq_document_revision", "document", type_="unique")
    op.create_unique_constraint("uq_document_revision", "document", ["category", "section", "document_no", "revision"])
def downgrade():
    op.drop_constraint("uq_document_revision", "document", type_="unique")
    op.create_unique_constraint("uq_document_revision", "document", ["category", "document_no", "revision"])
    op.drop_index("ix_document_section", table_name="document")
    op.drop_column("document", "section")
