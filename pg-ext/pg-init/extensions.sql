-- 1. 확장 기능 설치
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_search;

-- 2. 원본 지식 테이블 (source_knowledge)
CREATE TABLE IF NOT EXISTS source_knowledge (
    id SERIAL PRIMARY KEY,
    content TEXT NOT NULL,
    process TEXT,
    subject TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 3. 청크 테이블 (source_chunk)
CREATE TABLE IF NOT EXISTS source_chunk (
    id SERIAL PRIMARY KEY,
    content TEXT NOT NULL,
    chunk_index INTEGER NOT NULL,
    chunk_version TEXT NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    -- UPSERT를 위한 고유 제약 조건 (코드에서 uq_... 참조 중)
    CONSTRAINT uq_source_chunk_content_hash_chunk_index_chunk_version UNIQUE (content, chunk_index, chunk_version)
);

-- 4. 원본-청크 매핑 테이블 (map_source_chunk)
CREATE TABLE IF NOT EXISTS map_source_chunk (
    id SERIAL PRIMARY KEY,
    chunk_id INTEGER REFERENCES source_chunk(id),
    source_id INTEGER REFERENCES source_knowledge(id),
    source_name TEXT NOT NULL,
    UNIQUE(chunk_id, source_id)
);

-- 5. 벡터 저장 테이블 (source_chunk_vec)
CREATE TABLE IF NOT EXISTS source_chunk_vec (
    id SERIAL PRIMARY KEY,
    chunk_id INTEGER REFERENCES source_chunk(id),
    chunk_vec vector(768), -- jhgan/ko-sroberta-multitask 모델은 768차원임
    vec_model_name TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_source_chunk_vec_chunk_id_vec_model_name UNIQUE (chunk_id, vec_model_name)
);