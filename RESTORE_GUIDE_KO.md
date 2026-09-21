# 복구 안내

1. GitHub `main` 브랜치의 최신 소스를 배포합니다.
2. AI SPACE PostgreSQL을 준비하고 DB 환경변수가 자동 주입되었는지 확인합니다.
3. 별도 보관한 PostgreSQL 덤프를 운영 DB에 복원합니다.
4. `/app/user_data` 백업을 같은 경로에 복원합니다.
5. `flask --app app db upgrade`를 한 번 실행합니다.
6. 애플리케이션 재시작 후 `/health`에서 PostgreSQL 읽기·쓰기 상태를 확인합니다.

초기 관리자 환경변수는 사용자 테이블이 비어 있을 때만 사용됩니다. 기존 DB 복원 후에는 관리자 비밀번호를 재설정하지 않습니다.

