"""GMP labeling and package master samples"""
from alembic import op
import sqlalchemy as sa
import uuid

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

def upgrade():
    asset = op.create_table(
        "labeling_asset",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("standard", sa.String(10), nullable=False, server_default="GMP"),
        sa.Column("item_type", sa.String(40), nullable=False),
        sa.Column("item_name", sa.String(100), nullable=False),
        sa.Column("product_name", sa.String(200), nullable=False, server_default=""),
        sa.Column("control_no", sa.String(100), nullable=False, server_default=""),
        sa.Column("revision", sa.String(50), nullable=False, server_default="-"),
        sa.Column("effective_date", sa.Date()),
        sa.Column("status", sa.String(30), nullable=False, server_default="preparing"),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("file_name", sa.String(255)),
        sa.Column("stored_name", sa.String(255)),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("user.id")),
        sa.Column("updated_by", sa.Uuid(), sa.ForeignKey("user.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_labeling_asset_type", "labeling_asset", ["standard", "item_type"])
    op.create_index("ix_labeling_asset_status", "labeling_asset", ["status"])
    rows=[
        ("vial","바이알"),("blister","블리스터 포장 완제품"),("ifu","IFU"),
        ("quick_guide","퀵가이드"),("product_box","제품박스")
    ]
    op.bulk_insert(asset, [{
        "id": uuid.UUID(f"1abe1100-0004-4000-8000-{i:012d}"),
        "standard": "GMP", "item_type": slug, "item_name": name,
        "product_name": "", "control_no": "", "revision": "-",
        "status": "preparing", "description": "최신 시안과 관리번호를 등록해 주세요."
    } for i,(slug,name) in enumerate(rows,1)])

def downgrade():
    op.drop_table("labeling_asset")
