import sys
from pathlib import Path

current_file_path = Path(__file__).resolve()
project_root = current_file_path.parents[3]
sys.path.append(str(project_root))

import os
from dotenv import load_dotenv
from typing import List, Dict, Any
from datasets import load_dataset
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from tqdm import tqdm

from src.pgdb.pg_crud import PGDB

env_path = project_root / "settings" / ".env.poc"
load_dotenv(dotenv_path=env_path)

PG_HOST = os.getenv("PG1_HOST")
PG_PORT = os.getenv("PG1_PORT")
PG_DB = os.getenv("PG1_DATABASE")
PG_USER = os.getenv("PG1_USERNAME")
PG_PASS = os.getenv("PG1_PASSWORD")

DATABASE_URL = f"postgresql://{PG_USER}:{PG_PASS}@{PG_HOST}:{PG_PORT}/{PG_DB}"

DATASET_CONFIGS = [
    ("allganize/RAG-Evaluation-Dataset-KO", "test", ["question", "target_answer"], "allganize_policy"),
    ("BCCard/BCCard-Finance-Kor-QnA", "train", ["instruction", "input", "output", "question", "answer"], "bccard_qna"),
    ("kifai/KoInFoBench", "train", ["instruction", "input", "output", "text"], "finance_corpus_wiki") 
]

EMBEDDING_MODEL_NAME = "jhgan/ko-sroberta-multitask"

print(f"임베딩 모델({EMBEDDING_MODEL_NAME}) 로드 중...")
embeddings = HuggingFaceEmbeddings(
    model_name=EMBEDDING_MODEL_NAME,
    model_kwargs={'device': 'mps'}, # mac -> mps ,  
    encode_kwargs={'normalize_embeddings': True}
)

def load_raw_data() -> List[Dict[str, Any]]:
    print("데이터셋 다운로드 및 통합 중...")
    unified_data = []
    
    for repo_id, split, text_cols, source_name in DATASET_CONFIGS:
        try:
            print(f" - {repo_id} 로드 중...")
            dataset = load_dataset(repo_id, split=split)
            
            for item in dataset:
                combined_text = []
                for col in text_cols:
                    if col in item and item[col]:
                        combined_text.append(f"{col}: {str(item[col])}")
                
                if combined_text:
                    unified_data.append({
                        "content": "\n".join(combined_text),
                        "metadata": {
                            "source_type": source_name,
                            "original_repo": repo_id,
                        }
                    })
        except Exception as e:
            print(f"{repo_id} 로드 실패: {e}")
            
    print(f"총 {len(unified_data)}개의 원본 문서 로드 완료.")
    return unified_data

def clear_existing_data(db: PGDB) -> None:
    print("\n기존 테이블 데이터 초기화 및 스키마 수정 진행 중...")
    
    # 1. 기존 데이터 초기화
    truncate_sql = """
        TRUNCATE TABLE source_knowledge, source_chunk, source_chunk_vec, map_source_chunk CASCADE;
    """
    db.execute_write(truncate_sql)
    
    # 2. 벡터 컬럼 차원 수를 768로 강제 변경
    try:
        alter_sql = """
            ALTER TABLE source_chunk_vec ALTER COLUMN chunk_vec TYPE vector(768);
        """
        db.execute_write(alter_sql)
        print("벡터 차원 수(768) 스키마 수정 완료.")
    except Exception as e:
        print(f"스키마 수정 중 알림 (이미 768이거나 다른 이유): {e}")

    print("기존 데이터 초기화 완료.")

def run_ingestion_pipeline() -> None:
    print("=== RAG_FRAMEWORK 통합 데이터 주입 시작 ===")
    
    try:
        db = PGDB(db_url=DATABASE_URL)
    except Exception as e:
        print(f"DB 연결 실패. 설정을 확인하세요: {e}")
        return

    clear_existing_data(db)

    raw_data = load_raw_data()
    if not raw_data:
        print("적재할 데이터가 없습니다.")
        return

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=350,
        chunk_overlap=50,
        separators=["\n\n", "\n", ".", "?", "!", " ", ""]
    )

    print("\nDB 적재 및 텍스트 청킹 진행 중...")
    
    # 중복 임베딩을 방지하기 위한 set
    seen_chunk_ids = set()
    all_chunks_for_embedding = []

    for doc in tqdm(raw_data, desc="Processing Documents"):
        # A. 원본 데이터 적재
        sql_insert_raw = """
            INSERT INTO source_knowledge (content, process, subject) 
            VALUES (:content, :process, :subject) 
            RETURNING id
        """
        raw_res = db.execute_write(
            sql_insert_raw, 
            {
                "content": doc["content"], 
                "process": "ingested", 
                "subject": doc["metadata"]["source_type"]
            }, 
            returning=True
        )
        source_id = raw_res[0]["id"]

        # B. 청킹 수행
        chunks = text_splitter.split_text(doc["content"])
        
        for index, chunk_text in enumerate(chunks):
            # C. 청크 데이터 적재 (UPSERT 처리)
            # 이미 존재하는 해시값이면 에러를 내지 않고 content를 덮어쓰며 기존 id를 반환합니다.
            sql_insert_chunk = """
                INSERT INTO source_chunk (content, chunk_index, chunk_version) 
                VALUES (:content, :chunk_index, :chunk_version) 
                ON CONFLICT ON CONSTRAINT uq_source_chunk_content_hash_chunk_index_chunk_version
                DO UPDATE SET content = EXCLUDED.content
                RETURNING id
            """
            chunk_res = db.execute_write(
                sql_insert_chunk,
                {
                    "content": chunk_text,
                    "chunk_index": index,
                    "chunk_version": "v1"
                },
                returning=True
            )
            chunk_id = chunk_res[0]["id"]

            # D. 매핑 테이블 적재 (중복 매핑 무시)
            sql_insert_map = """
                INSERT INTO map_source_chunk (chunk_id, source_id, source_name) 
                VALUES (:chunk_id, :source_id, :source_name)
                ON CONFLICT ON CONSTRAINT uq_map_source_chunk_chunk_id_source_id_source_name
                DO NOTHING
            """
            db.execute_write(
                sql_insert_map,
                {
                    "chunk_id": chunk_id,
                    "source_id": source_id,
                    "source_name": "knowledge"
                }
            )

            # E. 새로 생성된(또는 아직 벡터가 안 만들어진) 청크만 임베딩 리스트에 추가
            if chunk_id not in seen_chunk_ids:
                seen_chunk_ids.add(chunk_id)
                all_chunks_for_embedding.append({
                    "chunk_id": chunk_id,
                    "content": chunk_text
                })

    print(f"\n총 {len(all_chunks_for_embedding)}개의 고유 청크가 필터링되어 임베딩 대기열에 들어갔습니다.")

    print("로컬 임베딩 변환 중...")
    texts_to_embed = [c["content"] for c in all_chunks_for_embedding]
    
    batch_size = 100
    all_vectors = []
    
    for i in tqdm(range(0, len(texts_to_embed), batch_size), desc="Embedding Batches"):
        batch_texts = texts_to_embed[i:i + batch_size]
        batch_vectors = embeddings.embed_documents(batch_texts)
        all_vectors.extend(batch_vectors)

    print("생성된 벡터를 DB에 대량 적재(Bulk Insert) 합니다...")
    vec_insert_data = []
    for chunk_meta, vector in zip(all_chunks_for_embedding, all_vectors):
        vec_insert_data.append((
            chunk_meta["chunk_id"],
            vector,
            EMBEDDING_MODEL_NAME
        ))

    db.bulk_insert(
        table_name="source_chunk_vec",
        columns=["chunk_id", "chunk_vec", "vec_model_name"],
        data=vec_insert_data,
        page_size=1000
    )

    print("\n데이터 주입 파이프라인 완주 성공! 중복 제거 및 모든 테이블 적재가 완료되었습니다.")
    db.close()

if __name__ == "__main__":
    run_ingestion_pipeline()