FROM postgres:17-bookworm AS pgvector_builder

ARG PGVECTOR_VERSION=v0.7.4

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      git build-essential postgresql-server-dev-17 ca-certificates && \
    rm -rf /var/lib/apt/lists/*

RUN git clone --branch ${PGVECTOR_VERSION} --depth 1 \
      https://github.com/pgvector/pgvector.git /tmp/pgvector && \
    cd /tmp/pgvector && \
    make && \
    make install

# --- #

FROM postgres:17-bookworm

ARG PG_SEARCH_VERSION=0.21.4  # ParadeDB pg_search 버전
ARG DEBIAN_CODENAME=bookworm  # Debian 12
ARG TARGETARCH
ENV PARADE_ARCH=${TARGETARCH:-amd64}

# pg_search
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      ca-certificates curl libicu-dev && \
    rm -rf /var/lib/apt/lists/*

# pg_search
RUN set -eux; \
    curl -L \
      "https://github.com/paradedb/paradedb/releases/download/v${PG_SEARCH_VERSION}/postgresql-17-pg-search_${PG_SEARCH_VERSION}-1PARADEDB-${DEBIAN_CODENAME}_${PARADE_ARCH}.deb" \
      -o /tmp/pg_search.deb && \
    apt-get update && \
    apt-get install -y /tmp/pg_search.deb && \
    rm -f /tmp/pg_search.deb && \
    rm -rf /var/lib/apt/lists/*

# pgvector
COPY --from=pgvector_builder /usr/lib/postgresql/17/lib/ /usr/lib/postgresql/17/lib/
COPY --from=pgvector_builder /usr/share/postgresql/17/extension/ /usr/share/postgresql/17/extension/

# pg-init
COPY pg-init/extensions.sql /docker-entrypoint-initdb.d/extensions.sql
