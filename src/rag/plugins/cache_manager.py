import os
import numpy as np
from redis import Redis
from redis.commands.search.field import TextField, VectorField
from redis.commands.search.index_definition import IndexDefinition, IndexType
from redis.commands.search.query import Query
from sentence_transformers import SentenceTransformer

from src.common.logger import get_logger
from settings.config import cfg  # 중앙 설정 관리자 임포트

logger = get_logger(__name__)

class SemanticCacheManager:
    def __init__(self, host: str = cfg.REDIS_HOST, port: int = cfg.REDIS_PORT, index_name: str = cfg.REDIS_INDEX_NAME):
        """
        설정값(cfg)을 기본값으로 사용하여 Redis 및 임베딩 모델 초기화
        """
        # 1. Redis 연결
        self.redis_client = Redis(host=host, port=port, decode_responses=True)
        self.index_name = index_name
        
        # 2. 임베딩 모델 로드
        logger.info(f"[Cache] 임베딩 모델 로딩 중... (Host: {host}:{port})")
        self.embedder = SentenceTransformer("jhgan/ko-sroberta-multitask")
        self.vector_dim = self.embedder.get_sentence_embedding_dimension()
        
        # 3. 인덱스 초기화
        self._setup_index()

    def _setup_index(self):
        """Redis에 벡터 검색을 위한 인덱스 스키마가 없으면 생성"""
        try:
            self.redis_client.ft(self.index_name).info()
            logger.info(f"[Cache] Redis 인덱스({self.index_name}) 연동 완료.")
        except Exception:
            logger.info(f"[Cache] Redis 인덱스({self.index_name})를 새로 생성합니다.")
            
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
        """질문 벡터와 캐시된 벡터들을 비교하여 threshold 이상일 경우 답변을 반환"""
        try:
            query_vector = self.embedder.encode(query).astype(np.float32).tobytes()
            
            q = Query(f"*=>[KNN 1 @query_vector $vec AS score]") \
                .return_fields("query", "response", "score") \
                .sort_by("score") \
                .dialect(2)
            
            res = self.redis_client.ft(self.index_name).search(q, {"vec": query_vector})
            
            if res.docs:
                distance = float(res.docs[0].score)
                similarity = 1.0 - distance
                
                if similarity >= threshold:
                    logger.info(f"[Cache HIT] 유사도: {similarity:.4f} (임계값: {threshold})")
                    return res.docs[0].response
                else:
                    logger.info(f"[Cache MISS] 최대 유사도 부족: {similarity:.4f} < {threshold}")
            else:
                logger.info("[Cache MISS] 캐시 저장소가 비어있습니다.")
        except Exception as e:
            logger.error(f"[Cache Error] 검색 중 오류 발생: {e}")
            
        return None

    def save_cache(self, query: str, response: str, ttl_seconds: int = 86400):
        """새로운 질문과 생성된 답변을 벡터와 함께 캐시에 저장"""
        try:
            query_vector = self.embedder.encode(query).astype(np.float32).tobytes()
            # Redis 키 생성 (특수문자 방지를 위해 간단한 해시 사용 권장)
            import hashlib
            query_hash = hashlib.md5(query.encode()).hexdigest()
            cache_key = f"cache:{query_hash}"
            
            self.redis_client.hset(cache_key, mapping={
                "query": query,
                "response": response,
                "query_vector": query_vector
            })
            
            self.redis_client.expire(cache_key, ttl_seconds)
            logger.debug(f"[Cache SAVED] 결과 저장 완료 (Key: {cache_key})")
        except Exception as e:
            logger.error(f"[Cache Error] 저장 중 오류 발생: {e}")

    def clear_cache(self):
        """Redis에 저장된 캐시 인덱스와 데이터를 모두 초기화"""
        try:
            self.redis_client.flushdb()
            logger.info("[Cache] 캐시 저장소가 완벽하게 초기화되었습니다.")
            self._setup_index()
        except Exception as e:
            logger.error(f"[Cache] 초기화 실패: {e}")