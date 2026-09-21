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
