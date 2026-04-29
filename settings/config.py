import os
from pydantic import BaseModel
from dotenv import load_dotenv
import yaml

# Path 설정
settings_dir = os.path.join(".", "settings")
env_path = os.path.join(settings_dir, ".env.poc")
yaml_path = os.path.join(settings_dir, "config.yaml")

# 환경 변수 로드
load_dotenv(env_path)

# 앱 설정 로드 (YAML)
yaml_datas: dict = {}
if os.path.exists(yaml_path):
    with open(yaml_path, "r", encoding="utf-8") as f:
        yaml_datas = yaml.safe_load(f) or {}

def get_nested_value(data_dict: dict, keys: list, default=None):
    current_value = data_dict
    for key in keys:
        if isinstance(current_value, dict):
            current_value = current_value.get(key, default)
            if current_value == default and key != keys[-1]:
                return default
        else:
            return default
    return current_value

class Config(BaseModel):
    """
    프로젝트 전체 설정 관리
    """
    # YAML 데이터 원본
    main: dict = yaml_datas

    # PostgreSQL (Vector DB)
    PG1_HOST:     str = os.getenv("PG1_HOST", "localhost")
    PG1_PORT:     str = os.getenv("PG1_PORT", "5432")
    PG1_DATABASE: str = os.getenv("PG1_DATABASE", "vector")
    PG1_USERNAME: str = os.getenv("PG1_USERNAME", "postgres")
    PG1_PASSWORD: str = os.getenv("PG1_PASSWORD", "password")

    # LLM & Openrouter
    LLM_PROVIDER: str = get_nested_value(yaml_datas, ["llm", "provider"], "openrouter")
    OPENROUTER_API_KEY:  str = os.getenv("OPENROUTER_API_KEY", "")
    OPENROUTER_BASE_URL: str = get_nested_value(yaml_datas, ["openrouter", "base_url"], "https://openrouter.ai/api/v1")
    MODEL_NAME:          str = get_nested_value(yaml_datas, ["openrouter", "model_name"], "google/gemini-2.5-flash-lite-001")

    # Redis (Semantic Cache)
    REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", 6379))
    REDIS_INDEX_NAME: str = os.getenv("REDIS_INDEX_NAME", "idx:rag_cache")

    # RabbitMQ (Message Queue)
    RABBITMQ_USER:     str = os.getenv("RABBITMQ_USER", "guest")
    RABBITMQ_PASSWORD: str = os.getenv("RABBITMQ_PASSWORD", "guest")
    RABBITMQ_HOST:     str = os.getenv("RABBITMQ_HOST", "localhost")
    RABBITMQ_PORT:     str = os.getenv("RABBITMQ_PORT", "5672")

    @property
    def RABBITMQ_URL(self) -> str:
        """AMQP 접속 URL 조합"""
        return f"amqp://{self.RABBITMQ_USER}:{self.RABBITMQ_PASSWORD}@{self.RABBITMQ_HOST}:{self.RABBITMQ_PORT}/"

    # Common
    LOGGER_LEVEL: int = int(os.getenv("LOGGER_LEVEL", 10))
    AGENT_MAX_TIMEOUT: float = get_nested_value(yaml_datas, ["agent", "max_timeout"], 30.0)
    AGENT_MAX_RETRIES: int = get_nested_value(yaml_datas, ["agent", "max_retries"], 3)

cfg = Config()

__all__ = ["cfg"]