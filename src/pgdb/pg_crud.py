import time
from typing import List, Dict, Any, Tuple, Union, Sequence, Iterator
from contextlib import contextmanager
import sqlalchemy
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import OperationalError, ProgrammingError, SQLAlchemyError, DBAPIError

from src.common.logger import get_logger

logger = get_logger(__name__)

ParamsType = Union[Dict[str, Any], Sequence[Dict[str, Any]], None]

class PGDB:
    """
    PostgreSQL 데이터베이스 연결 및 CRUD 작업을 관리하는 클래스.
    - 안전한 커넥션/트랜잭션 수명주기
    - SELECT 결과는 컨텍스트 내에서 소비 후 파이썬 객체로 반환
    """

    def __init__(
        self,
        db_url: str,
        *,
        connect_retries: int = 3,
        query_retries: int = 1,  # 읽기(SELECT)만 재시도
        connect_backoff_base_sec: float = 2.0,
        pool_size: int = 5,
        max_overflow: int = 10,
        pool_timeout: int = 30,
        pool_recycle: int = 1800,
        pool_pre_ping: bool = True,
        statement_timeout_ms: int|None = 10_000,
    ):
        self.db_url = db_url
        self.connect_retries = connect_retries
        self.query_retries = query_retries
        self.connect_backoff_base_sec = connect_backoff_base_sec

        self.pool_size = pool_size
        self.max_overflow = max_overflow
        self.pool_timeout = pool_timeout
        self.pool_recycle = pool_recycle
        self.pool_pre_ping = pool_pre_ping
        self.statement_timeout_ms = statement_timeout_ms

        self.engine: Engine|None = None
        self._connect()

    def _connect(self) -> None:
        connect_args: Dict[str, Any] = {}
        if self.statement_timeout_ms is not None:
            connect_args["options"] = f"-c statement_timeout={int(self.statement_timeout_ms)}"

        last_err: BaseException|None = None
        for i in range(self.connect_retries + 1):
            try:
                self.engine = create_engine(
                    self.db_url,
                    pool_pre_ping=self.pool_pre_ping,
                    pool_size=self.pool_size,
                    max_overflow=self.max_overflow,
                    pool_timeout=self.pool_timeout,
                    pool_recycle=self.pool_recycle,
                    connect_args=connect_args if connect_args else None,
                )
                with self.engine.connect() as conn:
                    conn.execute(text("SELECT 1"))
                logger.info("DB 연결 성공")
                return
            except OperationalError as e:
                last_err = e
                logger.warning("DB 연결 실패 (시도 %d/%d): %s", i + 1, self.connect_retries + 1, e)
                if i < self.connect_retries:
                    time.sleep(self.connect_backoff_base_sec**i)
            except Exception as e:
                last_err = e
                break

        raise ConnectionError(f"DB 연결 실패(재시도 {self.connect_retries}회): {last_err}") from last_err

    def _require_engine(self) -> Engine:
        if not self.engine:
            raise ConnectionError("데이터베이스 엔진이 초기화되지 않았습니다. 먼저 연결을 시도하세요.")
        return self.engine
    
    def close(self) -> None:
        if self.engine is not None:
            self.engine.dispose()
            logger.info("DB 엔진 dispose 완료")

    @staticmethod
    def _row_to_dict(row: Any) -> Dict[str, Any]:
        return dict(row._mapping)

    def _execute_with_retry_readonly(
        self,
        conn: Connection,
        sql_query: str,
        params: ParamsType = None,
    ) -> sqlalchemy.engine.CursorResult:
        last_err: BaseException|None = None
        for i in range(self.query_retries + 1):
            try:
                return conn.execute(text(sql_query), params)  # type: ignore[arg-type]
            except OperationalError as e:
                last_err = e
                logger.warning("읽기 쿼리 실행 실패(OperationalError) (시도 %d/%d): %s", i + 1, self.query_retries + 1, e)
                if i < self.query_retries:
                    time.sleep(1.0)
            except ProgrammingError as e:
                logger.error("읽기 쿼리 실행 실패(ProgrammingError): %s", e)
                raise
            except SQLAlchemyError as e:
                last_err = e
                logger.error("읽기 쿼리 실행 실패(SQLAlchemyError): %s", e)
                raise

        raise SQLAlchemyError(f"읽기 쿼리 실행 재시도 {self.query_retries}회 모두 실패: {last_err}") from last_err

    @contextmanager
    def transaction(self) -> Iterator[Connection]:
        engine = self._require_engine()
        with engine.connect() as conn:
            tx = conn.begin()
            try:
                yield conn
                tx.commit()
            except Exception:
                tx.rollback()
                logger.exception("트랜잭션 롤백")
                raise

    def fetch_one(self, sql_query: str, params: Dict[str, Any]|None = None) -> Dict[str, Any]|None:
        engine = self._require_engine()
        with engine.connect() as conn:
            result = self._execute_with_retry_readonly(conn, sql_query, params)
            row = result.fetchone()
            return self._row_to_dict(row) if row else None

    def fetch_all(self, sql_query: str, params: Dict[str, Any]|None = None) -> List[Dict[str, Any]]:
        engine = self._require_engine()
        with engine.connect() as conn:
            result = self._execute_with_retry_readonly(conn, sql_query, params)
            rows = result.fetchall()
            return [self._row_to_dict(r) for r in rows]

    def execute_write(
        self,
        sql_query: str,
        params: Dict[str, Any]|None = None,
        *,
        returning: bool = False,
    ) -> Union[int, List[Dict[str, Any]]]:
        with self.transaction() as conn:
            try:
                result = conn.execute(text(sql_query), params)
                if returning:
                    rows = result.fetchall()
                    return [self._row_to_dict(r) for r in rows]
                return int(result.rowcount or 0)
            except ProgrammingError:
                logger.exception("Write ProgrammingError")
                raise
            except DBAPIError as e:
                logger.exception("Write DBAPIError")
                raise
            except SQLAlchemyError:
                logger.exception("Write SQLAlchemyError")
                raise

    def bulk_insert(
        self,
        table_name: str,
        columns: List[str],
        data: List[Tuple],
        page_size: int = 1000,
        on_conflict: str = "",
    ) -> None:
        """
        대량의 데이터를 고속으로 INSERT 한다. on_conflict 파라미터로 충돌 제어를 추가할 수 있다.
        """
        engine = self._require_engine()

        if not data:
            logger.info("삽입할 데이터가 없음")
            return

        cols_str = ", ".join(columns)
        placeholders = ", ".join([f":{col}" for col in columns])
        
        # on_conflict 쿼리 결합
        insert_sql = f"INSERT INTO {table_name} ({cols_str}) VALUES ({placeholders}) {on_conflict}".strip()

        param_dicts: List[Dict[str, Any]] = [dict(zip(columns, row_tuple)) for row_tuple in data]

        logger.info("bulk_insert 시작: table=%s rows=%d page_size=%d", table_name, len(data), page_size)

        with engine.connect() as conn:
            with conn.begin():
                for i in range(0, len(param_dicts), page_size):
                    batch = param_dicts[i : i + page_size]
                    conn.execute(text(insert_sql), batch) 
                    logger.debug("bulk_insert batch 완료: %d~%d", i, min(i + page_size, len(param_dicts)))

        logger.info("bulk_insert 완료: table=%s rows=%d", table_name, len(data))