"""Annual VMP validation execution management"""
from alembic import op
import sqlalchemy as sa
import uuid
from datetime import date

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None

def upgrade():
    plan = op.create_table(
        "validation_plan",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("year", sa.Integer(), nullable=False, unique=True),
        sa.Column("vmp_no", sa.String(100), nullable=False, server_default=""),
        sa.Column("title", sa.String(250), nullable=False),
        sa.Column("issue_date", sa.Date()),
        sa.Column("owner", sa.String(100), nullable=False, server_default=""),
        sa.Column("status", sa.String(30), nullable=False, server_default="active"),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("user.id")),
        sa.Column("updated_by", sa.Uuid(), sa.ForeignKey("user.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    record = op.create_table(
        "validation_record",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("plan_id", sa.Uuid(), sa.ForeignKey("validation_plan.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("validation_type", sa.String(100), nullable=False),
        sa.Column("target_name", sa.String(250), nullable=False),
        sa.Column("equipment_no", sa.String(100), nullable=False, server_default=""),
        sa.Column("validation_item", sa.String(250), nullable=False),
        sa.Column("department", sa.String(100), nullable=False, server_default=""),
        sa.Column("cycle", sa.String(100), nullable=False, server_default=""),
        sa.Column("plan_doc_no", sa.String(100), nullable=False, server_default=""),
        sa.Column("report_doc_no", sa.String(100), nullable=False, server_default=""),
        sa.Column("last_completed_date", sa.Date()),
        sa.Column("next_due_date", sa.Date()),
        sa.Column("reminder_days", sa.Integer(), nullable=False, server_default="60"),
        sa.Column("status", sa.String(30), nullable=False, server_default="scheduled"),
        sa.Column("owner", sa.String(100), nullable=False, server_default=""),
        sa.Column("result_note", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("user.id")),
        sa.Column("updated_by", sa.Uuid(), sa.ForeignKey("user.id")),
        sa.Column("completed_by", sa.Uuid(), sa.ForeignKey("user.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_validation_record_plan_due", "validation_record", ["plan_id", "next_due_date"])
    op.create_index("ix_validation_record_status", "validation_record", ["status"])
    plan_id = uuid.UUID("5ced0010-0000-4000-8000-000000000001")
    op.bulk_insert(plan, [{
        "id": plan_id, "year": 2026, "vmp_no": "2026 VMP",
        "title": "2026년도 Validation Master Plan", "owner": "품질부서",
        "status": "active", "notes": "연도별 VMP에 따른 밸리데이션 이행현황"
    }])
    rows = [
        ("클린룸","클린룸2(1007호)","-","IQ/OQ/PQ","품질","1년","CVP250827","CVR250829",date(2025,10,27),date(2026,10,27),"scheduled"),
        ("감마멸균","멸균 공정","-","IQ/OQ (멸균선량결정)","품질","변경 시","-","GDE251121-02",date(2025,11,21),None,"event_based"),
        ("감마멸균","멸균 공정","-","PQ (Dose mapping)","품질","변경 시","-","G20251201-02",date(2025,12,1),None,"event_based"),
        ("포장","포장 공정","MP-M-004","IQ/OQ/PQ","제조","6개월","PVP-012","PVR-012",date(2025,12,1),date(2026,5,27),"scheduled"),
        ("충진","자동 충진 공정","MP-M-006","IQ/OQ/PQ","제조","1년","AFVP-001","AFVR-001",date(2025,12,8),date(2026,12,7),"scheduled"),
        ("소프트웨어","라벨프린터","MP-N-005","IQ/OQ/PQ","제조","1년","LPVP-001","LPVR-001",date(2026,1,16),date(2027,1,15),"scheduled"),
        ("운송","제품 운송","-","낙하,진동,저압,충격,적층 등","품질","변경 시","SVP-001","SVR-001",date(2026,9,4),None,"event_based"),
    ]
    table_rows=[]
    for i,row in enumerate(rows,1):
        table_rows.append({
            "id":uuid.uuid4(),"plan_id":plan_id,"sequence":i,
            "validation_type":row[0],"target_name":row[1],"equipment_no":row[2],
            "validation_item":row[3],"department":row[4],"cycle":row[5],
            "plan_doc_no":row[6],"report_doc_no":row[7],
            "last_completed_date":row[8],"next_due_date":row[9],
            "reminder_days":60,"status":row[10],"owner":row[4],
            "result_note":""
        })
    op.bulk_insert(record, table_rows)

def downgrade():
    op.drop_table("validation_record")
    op.drop_table("validation_plan")
