"""Split IFU, quick guide and product box by market"""
from alembic import op
import sqlalchemy as sa
import uuid

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None

SPLIT_TYPES = ("ifu", "quick_guide", "product_box")

def upgrade():
    op.add_column("labeling_asset", sa.Column("market_variant", sa.String(20), nullable=False, server_default="common"))
    op.execute("""UPDATE labeling_asset
        SET market_variant='domestic', market_scope='국내용'
        WHERE item_type IN ('ifu','quick_guide','product_box')""")
    bind = op.get_bind()
    sources = bind.execute(sa.text("""SELECT DISTINCT ON (product_code,item_type)
        standard, product_code, item_type, item_name, product_name, valid_until_note
        FROM labeling_asset
        WHERE item_type IN ('ifu','quick_guide','product_box')
        ORDER BY product_code,item_type,updated_at DESC""")).mappings().all()
    table = sa.table("labeling_asset",
        sa.column("id",sa.Uuid()), sa.column("standard",sa.String()),
        sa.column("item_type",sa.String()), sa.column("item_name",sa.String()),
        sa.column("product_code",sa.String()), sa.column("product_name",sa.String()),
        sa.column("market_scope",sa.String()), sa.column("market_variant",sa.String()),
        sa.column("valid_until_note",sa.String()), sa.column("control_no",sa.String()),
        sa.column("revision",sa.String()), sa.column("status",sa.String()),
        sa.column("description",sa.Text()), sa.column("image_hidden",sa.Boolean()))
    rows = []
    for source in sources:
        rows.append({
            "id": uuid.uuid4(), "standard": source["standard"],
            "item_type": source["item_type"], "item_name": source["item_name"],
            "product_code": source["product_code"], "product_name": source["product_name"],
            "market_scope": "해외용", "market_variant": "overseas",
            "valid_until_note": source["valid_until_note"] or "추후 개정 시",
            "control_no": "", "revision": "-", "status": "preparing",
            "description": "해외용 최신 시안과 관리번호를 등록해 주세요.",
            "image_hidden": False,
        })
    if rows:
        op.bulk_insert(table, rows)
    op.create_index("ix_labeling_asset_market_variant", "labeling_asset",
        ["standard","product_code","item_type","market_variant"])

def downgrade():
    op.drop_index("ix_labeling_asset_market_variant", table_name="labeling_asset")
    op.execute("DELETE FROM labeling_asset WHERE market_variant='overseas'")
    op.drop_column("labeling_asset", "market_variant")
