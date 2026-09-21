"""split labeling information by medical device product"""
from alembic import op
import sqlalchemy as sa
import uuid

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("labeling_asset", sa.Column("product_code", sa.String(30), nullable=True))
    op.add_column("labeling_asset", sa.Column("market_scope", sa.String(100), nullable=False, server_default="국내/해외향 공통"))
    op.add_column("labeling_asset", sa.Column("valid_until_note", sa.String(150), nullable=False, server_default="추후 개정 시"))
    op.execute("UPDATE labeling_asset SET product_code='medical', product_name='MedParkAllo' WHERE standard='GMP'")
    op.execute("""UPDATE labeling_asset SET control_no='VLB.012.MP(0.00).EN', revision='0.00',
        effective_date='2026-09-02', status='current',
        description='MedParkAllo(메디컬) 바이알 최신 라벨 시안. 국내/해외향 공통.'
        WHERE standard='GMP' AND product_code='medical' AND item_type='vial'""")
    bind=op.get_bind()
    source=bind.execute(sa.text("""SELECT item_type,item_name FROM labeling_asset
        WHERE standard='GMP' AND product_code='medical' ORDER BY item_type""")).fetchall()
    table=sa.table("labeling_asset",
        sa.column("id",sa.Uuid()),sa.column("standard",sa.String()),sa.column("product_code",sa.String()),
        sa.column("item_type",sa.String()),sa.column("item_name",sa.String()),sa.column("product_name",sa.String()),
        sa.column("control_no",sa.String()),sa.column("revision",sa.String()),sa.column("effective_date",sa.Date()),
        sa.column("status",sa.String()),sa.column("description",sa.Text()),sa.column("market_scope",sa.String()),
        sa.column("valid_until_note",sa.String()))
    rows=[]
    for i,(slug,name) in enumerate(source,1):
        vial=slug=="vial"
        rows.append({
            "id":uuid.UUID(f"1abe2200-0005-4000-8000-{i:012d}"),"standard":"GMP","product_code":"dental",
            "item_type":slug,"item_name":name,"product_name":"MedParkAlloD",
            "control_no":"VLB.013.MP(0.00).EN" if vial else "","revision":"0.00" if vial else "-",
            "effective_date":__import__("datetime").date(2026,9,2) if vial else None,
            "status":"current" if vial else "preparing",
            "description":"MedParkAlloD(덴탈) 바이알 최신 라벨 시안. 국내/해외향 공통." if vial else "최신 시안과 관리번호를 등록해 주세요.",
            "market_scope":"국내/해외향 공통","valid_until_note":"추후 개정 시"
        })
    op.bulk_insert(table,rows)
    op.alter_column("labeling_asset","product_code",nullable=False)
    op.create_index("ix_labeling_asset_product","labeling_asset",["standard","product_code","item_type"])

def downgrade():
    op.drop_index("ix_labeling_asset_product",table_name="labeling_asset")
    op.execute("DELETE FROM labeling_asset WHERE product_code='dental'")
    op.drop_column("labeling_asset","valid_until_note")
    op.drop_column("labeling_asset","market_scope")
    op.drop_column("labeling_asset","product_code")
