"""register medical and dental blister package masters"""
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None

def upgrade():
    op.execute("""UPDATE labeling_asset SET
        control_no='LB.012.MP(0.00).EN', revision='0.00', effective_date='2026-09-02',
        status='current', market_scope='국내/해외향 공통', valid_until_note='추후 개정 시',
        description='MedParkAllo(메디컬) 블리스터 포장 완제품 최신 시안. 국내/해외향 공통.'
        WHERE standard='GMP' AND product_code='medical' AND item_type='blister'""")
    op.execute("""UPDATE labeling_asset SET
        control_no='LB.013.MP(0.00).EN', revision='0.00', effective_date='2026-09-02',
        status='current', market_scope='국내/해외향 공통', valid_until_note='추후 개정 시',
        description='MedParkAlloD(덴탈) 블리스터 포장 완제품 최신 시안. 국내/해외향 공통.'
        WHERE standard='GMP' AND product_code='dental' AND item_type='blister'""")

def downgrade():
    op.execute("""UPDATE labeling_asset SET control_no='',revision='-',effective_date=NULL,status='preparing',
        description='최신 시안과 관리번호를 등록해 주세요.'
        WHERE standard='GMP' AND item_type='blister'""")
