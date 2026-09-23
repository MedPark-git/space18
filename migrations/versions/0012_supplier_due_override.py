"""Allow a supplier-specific next re-evaluation date"""
from alembic import op
import sqlalchemy as sa

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("supplier", sa.Column("next_due_override", sa.Date()))


def downgrade():
    op.drop_column("supplier", "next_due_override")
