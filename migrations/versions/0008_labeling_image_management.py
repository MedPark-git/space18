"""Allow current labeling artwork to be hidden or replaced"""
from alembic import op
import sqlalchemy as sa

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("labeling_asset", sa.Column("image_hidden", sa.Boolean(), nullable=False, server_default=sa.false()))

def downgrade():
    op.drop_column("labeling_asset", "image_hidden")
