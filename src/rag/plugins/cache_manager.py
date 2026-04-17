import os
import numpy as np
from redis import Redis
from redis.commands.search.field import TextField, VectorField
from redis.commands.search.index_definition import IndexDefinition, IndexType
from redis.commands.search.query import Query
from sentence_transformers import SentenceTransformer

from src.common.logger import get_logger

logger = get_logger(__name__)

class SemanticCacheManager:
    def __init__(self, host: str = "localhost", port: int = 6379, index_name: str = "idx:rag_cache"):
        # 1. Redis 연결
        self.redis_client = Redis(host=host, port=port, decode_responses=True)
        self.index_name = index_name
        
        # 2. 임베딩 모델 로드 (리트리버와 동일한 모델 사용 권장)
        logger.info("[Cache] 임베딩 모델 로딩 중...")
        self.embedder = SentenceTransformer("jhgan/ko-sroberta-multitask")
        self.vector_dim = self.embedder.get_sentence_embedding_dimension()
        
        # 3. 인덱스 초기화
        self._setup_index()

    def _setup_index(self):
        """Redis에 벡터 검색을 위한 인덱스 스키마가 없으면 생성합니다."""
        try:
            self.redis_client.ft(self.index_name).info()
            logger.info(f"[Cache] Redis 인덱스({self.index_name}) 연동 완료.")
        except Exception:
            logger.info(f"[Cache] Redis 인덱스({self.index_name})를 새로 생성합니다.")
            
            # FLAT 방식: 데이터가 많지 않은 캐시 환경에서 100% 정확한 완전 탐색 방식
            schema = (
                TextField("query"),
                TextField("response"),
                VectorField(
                    "query_vector",
                    "FLAT",
                    {
                        "TYPE": "FLOAT32",
                        "DIM": self.vector_dim,
                        "DISTANCE_METRIC": "COSINE",
                    }
                )
            )
            definition = IndexDefinition(prefix=["cache:"], index_type=IndexType.HASH)
            self.redis_client.ft(self.index_name).create_index(fields=schema, definition=definition)

    def check_cache(self, query: str, threshold: float = 0.90) -> str | None:
        """
        질문 벡터와 캐시된 벡터들을 비교하여 threshold 이상일 경우 답변을 반환합니다.
        """
        # 쿼리를 32비트 Float 바이너리 형태로 변환 (Redis 권장 규격)
        query_vector = self.embedder.encode(query).astype(np.float32).tobytes()
        
        # Redis KNN(K-Nearest Neighbors) 쿼리 작성 (가장 가까운 1개 검색)
        q = Query(f"*=>[KNN 1 @query_vector $vec AS score]") \
            .return_fields("query", "response", "score") \
            .sort_by("score") \
            .dialect(2)
        
        # 바이너리 파라미터 매핑 후 검색
        res = self.redis_client.ft(self.index_name).search(q, {"vec": query_vector})
        
        if res.docs:
            # 코사인 거리(Cosine Distance)를 코사인 유사도(Cosine Similarity)로 변환
            # 거리 0 = 유사도 1 (완벽 일치)
            distance = float(res.docs[0].score)
            similarity = 1.0 - distance
            
            if similarity >= threshold:
                logger.info(f"[Cache HIT] 유사도: {similarity:.4f} (임계값: {threshold}) -> 파이프라인 우회")
                return res.docs[0].response
            else:
                logger.info(f"[Cache MISS] 최대 유사도 부족: {similarity:.4f} < {threshold}")
        else:
            logger.info("[Cache MISS] 캐시 저장소가 비어있습니다.")
            
        return None

    def save_cache(self, query: str, response: str, ttl_seconds: int = 86400):
        """
        새로운 질문과 생성된 답변을 벡터와 함께 캐시에 저장합니다.
        """
        query_vector = self.embedder.encode(query).astype(np.float32).tobytes()
        cache_key = f"cache:{hash(query)}"
        
        # Hash 형태로 데이터 저장
        self.redis_client.hset(cache_key, mapping={
            "query": query,
            "response": response,
            "query_vector": query_vector
        })
        
        # TTL(만료 시간) 설정 - 기본 24시간
        self.redis_client.expire(cache_key, ttl_seconds)
        logger.debug(f"[Cache SAVED] 결과 저장 완료 (Key: {cache_key})")