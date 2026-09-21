# 서울 3-site 기술부(품질)

GMP·GTP 문서를 구분하여 관리하는 사내용 Flask 애플리케이션입니다.

## 운영 구성

- Python 3.11 / Flask / Gunicorn
- PostgreSQL / SQLAlchemy / psycopg
- 모든 업무 데이터는 PostgreSQL에 저장
- 첨부파일만 `/app/user_data`에 저장
- DB 시간 UTC 저장, 화면 Asia/Seoul 표시

## 시작

AI SPACE가 주입하는 DB 환경변수와 `SECRET_KEY`가 필요합니다. 최초 사용자 테이블이 비어 있을 때만 `BOOTSTRAP_ADMIN_ID`, `BOOTSTRAP_ADMIN_PASSWORD`, `BOOTSTRAP_ADMIN_NAME`으로 관리자를 생성합니다. 실제 비밀번호는 이 저장소에 기록하지 않습니다.

```bash
flask --app app db upgrade
gunicorn --workers 2 --threads 4 --timeout 120 --bind 0.0.0.0:${PORT:-8000} app:app
```

헬스체크: `GET /health`

