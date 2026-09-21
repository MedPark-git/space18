"""GMP customer complaint management"""
from alembic import op
import sqlalchemy as sa
import uuid

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

def upgrade():
    complaint = op.create_table(
        "complaint",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("complaint_no", sa.String(40), nullable=False, unique=True),
        sa.Column("standard", sa.String(10), nullable=False, server_default="GMP"),
        sa.Column("market", sa.String(20), nullable=False),
        sa.Column("country", sa.String(100), nullable=False),
        sa.Column("province", sa.String(50)),
        sa.Column("receipt_date", sa.Date(), nullable=False),
        sa.Column("customer_name", sa.String(200), nullable=False),
        sa.Column("product_name", sa.String(200), nullable=False),
        sa.Column("model_name", sa.String(100), nullable=False),
        sa.Column("lot_no", sa.String(100), nullable=False),
        sa.Column("volume", sa.String(50), nullable=False, server_default=""),
        sa.Column("shipment_qty", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("shipment_type", sa.String(100), nullable=False, server_default=""),
        sa.Column("complaint_qty", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("complaint_type", sa.String(150), nullable=False),
        sa.Column("original_summary", sa.String(250), nullable=False, server_default=""),
        sa.Column("complaint_detail", sa.Text(), nullable=False),
        sa.Column("investigation", sa.Text(), nullable=False, server_default=""),
        sa.Column("investigation_result", sa.Text(), nullable=False, server_default=""),
        sa.Column("action_detail", sa.Text(), nullable=False, server_default=""),
        sa.Column("capa_required", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("handling_type", sa.String(100), nullable=False, server_default=""),
        sa.Column("handled_date", sa.Date()),
        sa.Column("status", sa.String(30), nullable=False, server_default="received"),
        sa.Column("closure_reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("owner", sa.String(100), nullable=False, server_default=""),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("user.id")),
        sa.Column("updated_by", sa.Uuid(), sa.ForeignKey("user.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_complaint_market", "complaint", ["market"])
    op.create_index("ix_complaint_province", "complaint", ["province"])
    op.create_index("ix_complaint_receipt_date", "complaint", ["receipt_date"])
    op.create_index("ix_complaint_status", "complaint", ["status"])
    op.bulk_insert(complaint, [{
        "id": uuid.UUID("d286cd26-0901-4260-9001-000000000001"),
        "complaint_no": "GMP-C-2026-001",
        "standard": "GMP",
        "market": "domestic",
        "country": "한국",
        "province": "서울",
        "receipt_date": __import__("datetime").date(2026, 9, 1),
        "customer_name": "홍제탑치과",
        "product_name": "MedParkAlloD",
        "model_name": "S1-ALLO-DS015",
        "lot_no": "SD260708P101",
        "volume": "0.3 cc",
        "shipment_qty": 22,
        "shipment_type": "무상 발주",
        "complaint_qty": 22,
        "complaint_type": "사용 불만 / 수화 후 성상·점도 이상",
        "original_summary": "사용 불만(수화 안됨)",
        "complaint_detail": "가이드에 따라 0.2 mL로 수화를 진행했으나 제품이 물처럼 흐르고 질퍽한 상태가 됨. 수화량을 0.15 mL 및 0.1 mL로 줄여도 동일한 현상이 발생함.",
        "investigation": "고객이 제시한 수화량을 포함하여 조건별 수화시험을 진행함.",
        "investigation_result": "조건별 수화시험 결과 이상 없음.",
        "action_detail": "조건별 수화시험 완료 및 결과 확인.",
        "capa_required": False,
        "handling_type": "기타",
        "handled_date": __import__("datetime").date(2026, 9, 8),
        "status": "completed",
        "closure_reason": "시험 결과 이상이 확인되지 않아 별도의 시정·예방조치 없이 종결.",
        "owner": "품질부서",
    }])

def downgrade():
    op.drop_table("complaint")
