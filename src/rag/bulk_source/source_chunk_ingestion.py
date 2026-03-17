from typing import List, Dict, Any
# from src.pgdb.pg_crud import ... (필요한 DB 조작 함수 임포트 예정)

def load_raw_data(source_path: str) -> List[Dict[str, Any]]:
    """데이터소스(Hugging Face, CSV, JSON 등)로부터 원본 데이터를 로드합니다."""
    raise NotImplementedError("새로운 도메인에 맞는 데이터 로드 로직 구현이 필요합니다.")

def chunk_documents(raw_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """로드된 원본 데이터를 적절한 크기의 청크(Chunk)로 분할합니다."""
    raise NotImplementedError("데이터 특성에 맞는 청킹 전략(예: RecursiveCharacterTextSplitter) 구현이 필요합니다.")

def embed_chunks(chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """분할된 청크 텍스트를 벡터 임베딩으로 변환합니다."""
    raise NotImplementedError("사용할 임베딩 모델 호출 로직이 필요합니다.")

def ingest_to_vector_db(embedded_chunks: List[Dict[str, Any]]) -> None:
    """임베딩이 완료된 청크와 메타데이터를 pgvector 데이터베이스에 적재합니다."""
    raise NotImplementedError("DB 세션 관리 및 데이터 삽입 로직이 필요합니다.")

def run_ingestion_pipeline(source_path: str) -> None:
    """
    [데이터 인제스천 파이프라인 흐름 제어]
    데이터 로드 -> 청킹 -> 임베딩 -> DB 적재를 순차적으로 실행합니다.
    """
    print(f"[{source_path}] 데이터 인제스천 파이프라인 시작...")
    
    raw_data = load_raw_data(source_path)
    chunks = chunk_documents(raw_data)
    embedded_chunks = embed_chunks(chunks)
    ingest_to_vector_db(embedded_chunks)
    
    print("데이터 인제스천 파이프라인 완료!")

if __name__ == "__main__":
    # TODO: 도메인 확정 후 실제 데이터 경로로 변경
    DUMMY_SOURCE_PATH = "path/to/new_domain_data" 
    # run_ingestion_pipeline(DUMMY_SOURCE_PATH)