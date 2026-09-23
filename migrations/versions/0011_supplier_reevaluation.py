"""Supplier qualification and periodic re-evaluation alerts"""
from alembic import op
import sqlalchemy as sa

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade():
    supplier = op.create_table(
        "supplier",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False, unique=True),
        sa.Column("purchase_item", sa.String(250), nullable=False, server_default=""),
        sa.Column("contact_person", sa.String(100), nullable=False, server_default=""),
        sa.Column("business_no", sa.String(50), nullable=False, server_default=""),
        sa.Column("address", sa.String(400), nullable=False, server_default=""),
        sa.Column("phone", sa.String(100), nullable=False, server_default=""),
        sa.Column("impact_grade", sa.String(1), nullable=False),
        sa.Column("initial_approval_date", sa.Date(), nullable=False),
        sa.Column("current_score", sa.Integer()),
        sa.Column("reminder_days", sa.Integer(), nullable=False, server_default="90"),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("user.id")),
        sa.Column("updated_by", sa.Uuid(), sa.ForeignKey("user.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    evaluation = op.create_table(
        "supplier_evaluation",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("supplier_id", sa.Uuid(), sa.ForeignKey("supplier.id", ondelete="CASCADE"), nullable=False),
        sa.Column("evaluation_date", sa.Date(), nullable=False),
        sa.Column("score", sa.Integer()),
        sa.Column("result", sa.String(30), nullable=False, server_default="approved"),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("evaluated_by", sa.Uuid(), sa.ForeignKey("user.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_supplier_name", "supplier", ["name"])
    op.create_index("ix_supplier_grade_active", "supplier", ["impact_grade", "is_active"])
    op.create_index("ix_supplier_evaluation_supplier_date", "supplier_evaluation", ["supplier_id", "evaluation_date"])

def downgrade():
    op.drop_table("supplier_evaluation")
    op.drop_table("supplier")
