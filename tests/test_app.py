import pytest
from app import create_app, db, User

@pytest.fixture()
def app(tmp_path):
    app = create_app({
        "TESTING": True,
        "SECRET_KEY": "test-secret",
        "SQLALCHEMY_DATABASE_URI": "sqlite+pysqlite:///:memory:",
        "SQLALCHEMY_ENGINE_OPTIONS": {},
        "WTF_CSRF_ENABLED": False,
        "UPLOAD_FOLDER": str(tmp_path),
        "SESSION_COOKIE_SECURE": False,
    })
    with app.app_context():
        db.create_all()
        admin = User(login_id="admin", name="관리자", role="admin", must_change_password=False)
        admin.set_password("StrongPass123")
        viewer = User(login_id="viewer", name="조회자", role="viewer", must_change_password=False)
        viewer.set_password("StrongPass123")
        db.session.add_all([admin, viewer]); db.session.commit()
    yield app

def login(client, user="admin"):
    return client.post("/login", data={"login_id": user, "password": "StrongPass123"})

def test_unauthenticated_redirect_and_api_401(app):
    client = app.test_client()
    assert client.get("/").status_code == 302
    assert client.get("/api/session").status_code == 401

def test_login_logout(app):
    client = app.test_client()
    assert login(client).status_code == 302
    assert client.get("/").status_code == 200
    assert client.post("/logout").status_code == 302
    assert client.get("/").status_code == 302

def test_viewer_cannot_create_document(app):
    client = app.test_client(); login(client, "viewer")
    response = client.post("/documents/GMP", data={"document_no":"G-1", "title":"시험"})
    assert response.status_code == 403

def test_admin_can_create_and_categories_are_separate(app):
    client = app.test_client(); login(client)
    response = client.post("/documents/GMP", data={"document_no":"G-1", "title":"GMP 시험", "revision":"0", "status":"draft"})
    assert response.status_code == 302
    assert "GMP 시험" in client.get("/documents/GMP").get_data(as_text=True)
    assert "GMP 시험" not in client.get("/documents/GTP").get_data(as_text=True)

def test_password_hash_is_not_plaintext(app):
    with app.app_context():
        user = db.session.scalar(db.select(User).where(User.login_id == "admin"))
        assert user.password_hash != "StrongPass123"
        assert user.check_password("StrongPass123")

def test_forged_role_and_status_are_rejected(app):
    client = app.test_client(); login(client)
    assert client.post("/admin/users", data={
        "login_id":"bad-role", "name":"비정상", "temporary_password":"StrongPass123", "role":"superuser"
    }).status_code == 400
    assert client.post("/documents/GMP", data={
        "document_no":"G-2", "title":"비정상 상태", "revision":"0", "status":"confirmed"
    }).status_code == 400

def test_gmp_and_gtp_work_indexes_are_separate(app):
    client = app.test_client(); login(client)
    gmp = client.get("/work/GMP").get_data(as_text=True)
    gtp = client.get("/work/GTP").get_data(as_text=True)
    assert "외부출처문서" in gmp and "구매관리" in gmp and "데이터 분석" in gmp
    assert "외부출처문서" not in gtp and "구매관리" not in gtp and "데이터 분석" not in gtp
    assert "문서 및 기록관리" in gmp and "문서 및 기록관리" in gtp

def test_same_document_number_can_be_used_in_different_sections(app):
    client = app.test_client(); login(client)
    payload = {"document_no":"SHARED-1", "title":"구분 시험", "revision":"0", "status":"draft"}
    assert client.post("/documents/GMP/external", data=payload).status_code == 302
    assert client.post("/documents/GMP/purchasing", data=payload).status_code == 302
    assert "구분 시험" in client.get("/documents/GMP/external").get_data(as_text=True)
    assert "구분 시험" in client.get("/documents/GMP/purchasing").get_data(as_text=True)
    assert "구분 시험" not in client.get("/documents/GTP/records").get_data(as_text=True)
