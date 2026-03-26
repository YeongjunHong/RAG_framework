# Migration Guide

### 커맨드 설명
```sh
# 현재 DB 버전을 최신으로 지정
alembic -c ./settings/alembic.ini stamp head

# 새 마이그레이션 파일 생성
alembic -c ./settings/alembic.ini revision --autogenerate -m "add"

# 현재 DB를 최신 마이그레이션 버전까지 반영
alembic -c ./settings/alembic.ini upgrade head

# 현재 DB 마이그레이션 버전 확인
alembic -c ./settings/alembic.ini current

# 마이그레이션 히스토리 확인
alembic -c ./settings/alembic.ini history
```

---

### init
```sh
alembic -c ./settings/alembic.ini init ./src/pgdb
alembic -c ./settings/alembic.ini stamp head
```

---

### migration

1. `./src/pgdb/schema.py` 스키마 변경

2. 마이그레이션 파일 생성
    ```sh
    alembic -c ./settings/alembic.ini revision --autogenerate -m "add"
    ```

3. 마이그레이션 파일 검토 (tsvector, vector 수동 정의 필수)

4. 마이그레이션 파일 반영
    ```sh
    alembic -c ./settings/alembic.ini upgrade head
    ```

---

### rollback
```sh
# 단계별 롤백
alembic -c ./settings/alembic.ini downgrade -1

# 특정 버전까지 롤백
alembic -c ./settings/alembic.ini downgrade 1b72c91d

# 모든 마이그레이션 취소
alembic -c ./settings/alembic.ini downgrade base
```