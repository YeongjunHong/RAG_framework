import sys
import os
import hashlib
from pathlib import Path
from typing import List, Dict, Any, Set
from dotenv import load_dotenv
from datasets import load_dataset
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
import torch
from tqdm import tqdm


current_file_path = Path(__file__).resolve()
project_root = current_file_path.parents[3]
sys.path.append(str(project_root))

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

def generate_hash(text: str) -> str:
    """텍스트의 SHA-256 해시값을 생성합니다."""
    return hashlib.sha256(text.encode('utf-8')).hexdigest()

# 파라미터(target_domain) 추가 및 필터링 로직 반영
def load_raw_data(target_domain: str = None) -> List[Dict[str, Any]]:
    print(f"데이터셋 다운로드 및 통합 중... (타겟: {target_domain or 'ALL'})")
    unified_data = []
    
    for repo_id, split, text_cols, source_name in DATASET_CONFIGS:
        # API에서 특정 도메인을 지정했는데, 현재 루프의 source_name과 다르면 스킵
        if target_domain and source_name != target_domain:
            continue
            
        try:
            print(f" - {repo_id} 로드 중...")
            dataset = load_dataset(repo_id, split=split)
            
            for item in dataset:
                combined_text = []
                for col in text_cols:
                    if col in item and item[col]:
                        combined_text.append(f"{col}: {str(item[col])}")
                
                if combined_text:
                    content = "\n".join(combined_text)
                    unified_data.append({
                        "content": content,
                        "content_hash": generate_hash(content), 
                        "metadata": {
                            "source_type": source_name,
                            "original_repo": repo_id,
                        }
                    })
        except Exception as e:
            print(f"[{repo_id}] 로드 실패: {e}")
            
    print(f"총 {len(unified_data)}개의 원본 문서 로드 완료.")
    return unified_data

def get_active_hashes_from_db(db: PGDB, subject: str) -> Dict[str, int]:
    """특정 도메인(subject)의 현재 활성화된 문서 해시와 ID를 가져옵니다."""
    sql = """
        SELECT id, content_hash 
        FROM source_knowledge 
        WHERE subject = :subject AND is_active = TRUE
    """
    rows = db.fetch_all(sql, {"subject": subject}) 
    
    if not rows:
        return {}
    return {row["content_hash"]: row["id"] for row in rows if row["content_hash"]}

def process_soft_delete(db: PGDB, source_ids_to_delete: List[int]) -> None:
    """더 이상 유효하지 않은 원본 문서와 연결된 청크들을 Soft Delete 처리합니다."""
    if not source_ids_to_delete:
        return

    print(f"{len(source_ids_to_delete)}개의 구버전/삭제 문서 Soft Delete 진행 중...")
    
    sql_disable_knowledge = """
        UPDATE source_knowledge 
        SET is_active = FALSE 
        WHERE id = ANY(:ids)
    """
    sql_disable_chunks = """
        UPDATE source_chunk 
        SET is_active = FALSE 
        FROM map_source_chunk msc
        WHERE source_chunk.id = msc.chunk_id
          AND msc.source_id = ANY(:ids)
    """
    
    db.execute_write(sql_disable_knowledge, {"ids": source_ids_to_delete})
    db.execute_write(sql_disable_chunks, {"ids": source_ids_to_delete})


def run_ingestion_pipeline(target_domain: str = None) -> None:
    print("=== [Zero-Downtime] 증분 업데이트 기반 데이터 주입 시작 ===")
    
    try:
        db = PGDB(db_url=DATABASE_URL)
    except Exception as e:
        print(f"DB 연결 실패: {e}")
        return

    raw_data = load_raw_data(target_domain=target_domain)
    if not raw_data:
        print(f"적재할 데이터가 없습니다.(도메인: {target_domain})")
        return

    data_by_subject = {}
    for doc in raw_data:
        subj = doc["metadata"]["source_type"]
        if subj not in data_by_subject:
            data_by_subject[subj] = []
        data_by_subject[subj].append(doc)

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=350, chunk_overlap=50, separators=["\n\n", "\n", ".", "?", "!", " ", ""]
    )

    all_chunks_for_embedding = []
    # 청크 중복 1차 방어 (파이썬 레벨)
    seen_chunk_ids = set()
    
    for subject, docs in data_by_subject.items():
        print(f"\n--- Domain: {subject} 분석 중 ---")
        new_hashes_map = {doc["content_hash"]: doc for doc in docs}
        new_hashes_set = set(new_hashes_map.keys())
        
        existing_hashes_map = get_active_hashes_from_db(db, subject)
        existing_hashes_set = set(existing_hashes_map.keys())
        
        hashes_to_insert = new_hashes_set - existing_hashes_set
        hashes_to_delete = existing_hashes_set - new_hashes_set
        hashes_unchanged = new_hashes_set & existing_hashes_set

        print(f" * 유지됨 (변경없음): {len(hashes_unchanged)} 건 (임베딩 스킵)")
        print(f" * 신규/수정됨 (Insert): {len(hashes_to_insert)} 건")
        print(f" * 삭제/만료됨 (Soft Delete): {len(hashes_to_delete)} 건")

        if hashes_to_delete:
            ids_to_delete = [existing_hashes_map[h] for h in hashes_to_delete]
            process_soft_delete(db, ids_to_delete)

        for h in tqdm(hashes_to_insert, desc=f"Ingesting New/Updated for {subject}"):
            doc = new_hashes_map[h]
            
            sql_insert_raw = """
                INSERT INTO source_knowledge (content, process, subject, content_hash, is_active) 
                VALUES (:content, :process, :subject, :content_hash, TRUE) 
                RETURNING id
            """
            raw_res = db.execute_write(
                sql_insert_raw, 
                {
                    "content": doc["content"], 
                    "process": "ingested", 
                    "subject": subject,
                    "content_hash": h
                }, 
                returning=True
            )
            source_id = raw_res[0]["id"]

            chunks = text_splitter.split_text(doc["content"])
            for index, chunk_text in enumerate(chunks):
                # 청크 중복 2차 방어 (DB 레벨 UPSERT)
                sql_insert_chunk = """
                    INSERT INTO source_chunk (content, chunk_index, chunk_version, is_active) 
                    VALUES (:content, :chunk_index, :chunk_version, TRUE) 
                    ON CONFLICT ON CONSTRAINT uq_source_chunk_content_hash_chunk_index_chunk_version
                    DO UPDATE SET is_active = TRUE
                    RETURNING id
                """
                chunk_res = db.execute_write(
                    sql_insert_chunk,
                    {"content": chunk_text, "chunk_index": index, "chunk_version": "v1"},
                    returning=True
                )
                chunk_id = chunk_res[0]["id"]

                sql_insert_map = """
                    INSERT INTO map_source_chunk (chunk_id, source_id, source_name) 
                    VALUES (:chunk_id, :source_id, :source_name)
                    ON CONFLICT DO NOTHING
                """
                db.execute_write(
                    sql_insert_map,
                    {"chunk_id": chunk_id, "source_id": source_id, "source_name": "knowledge"}
                )

                # 임베딩 대기열 중복 삽입 방지
                if chunk_id not in seen_chunk_ids:
                    seen_chunk_ids.add(chunk_id)
                    all_chunks_for_embedding.append({
                        "chunk_id": chunk_id,
                        "content": chunk_text
                    })

    if not all_chunks_for_embedding:
        print("\n새로 임베딩할 청크가 없습니다. 파이프라인을 종료합니다.")
        db.close()
        return

    print(f"\n총 {len(all_chunks_for_embedding)}개의 신규 고유 청크 임베딩 변환 시작...")
    
    print(f"임베딩 모델({EMBEDDING_MODEL_NAME}) 로드 중...")
    # embeddings = HuggingFaceEmbeddings(
    #     model_name=EMBEDDING_MODEL_NAME,
    #     model_kwargs={'device': 'mps'}, 
    #     encode_kwargs={'normalize_embeddings': True}
    # )
    device = "mps" if torch.backends.mps.is_available() else "cpu"
    print(f"사용 장치: {device}")

    embeddings = HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL_NAME,
        model_kwargs={'device': device}, 
        encode_kwargs={'normalize_embeddings': True}
)
    
    texts_to_embed = [c["content"] for c in all_chunks_for_embedding]
    batch_size = 100
    all_vectors = []
    
    for i in tqdm(range(0, len(texts_to_embed), batch_size), desc="Embedding Batches"):
        batch_texts = texts_to_embed[i:i + batch_size]
        batch_vectors = embeddings.embed_documents(batch_texts)
        all_vectors.extend(batch_vectors)

    print("생성된 벡터 DB Bulk Insert 중...")
    vec_insert_data = []
    for chunk_meta, vector in zip(all_chunks_for_embedding, all_vectors):
        vec_insert_data.append((
            chunk_meta["chunk_id"],
            vector,
            EMBEDDING_MODEL_NAME
        ))

    # 벡터 중복 3차 방어 (DB 레벨 IGNORE)
    db.bulk_insert(
        table_name="source_chunk_vec",
        columns=["chunk_id", "chunk_vec", "vec_model_name"],
        data=vec_insert_data,
        page_size=1000,
        on_conflict="ON CONFLICT ON CONSTRAINT uq_source_chunk_vec_chunk_id_vec_model_name DO NOTHING"
    )

    print("\n데이터 주입 파이프라인 완주 성공! Zero-Downtime 업데이트가 완료되었습니다.")
    db.close()

if __name__ == "__main__":
    run_ingestion_pipeline()