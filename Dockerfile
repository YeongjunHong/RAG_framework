FROM python:3.10-slim

# 1. uv 설치
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# 2. 의존성 설치 (로컬 .venv를 무시하고 새로 구축)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-cache

# 3. 소스 코드만 복사 (.dockerignore에 정의된 파일은 제외됨)
COPY . .

# 4. PATH 설정
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH=/app