import os
from pydantic import BaseModel
from dotenv import load_dotenv
import yaml


# path 설정
settings_dir = os.path.join(".", "settings")

env_path = os.path.join(settings_dir, ".env.poc")
# env_path = os.path.join(settings_dir, ".env.dev")
# env_path = os.path.join(settings_dir, ".env.stg")

yaml_path = os.path.join(settings_dir, "config.yaml")


# 환경 변수 로드
load_dotenv(env_path)


# 앱 설정 로드
yaml_datas: dict = {}
with open(yaml_path, "r", encoding="utf-8") as f:
    yaml_datas = yaml.safe_load(f)


def get_nested_value(data_dict: dict, keys: list, default=None):
    """
    중첩된 딕셔너리에서 키 경로를 따라 값을 찾아 반환
    경로 중 어느 하나라도 키가 존재하지 않으면 default 값을 반환

    Args:
        data_dict (dict): 값을 찾을 딕셔너리.
        keys (list): 찾고자 하는 키들의 리스트.
        default: 키 경로를 찾지 못했을 때 반환할 기본값.

    Returns:
        찾은 값 또는 default 값.
    """
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
    # YAML
    main: dict = yaml_datas

    # PG1
    PG1_HOST:     str = os.getenv("PG1_HOST", "")
    PG1_PORT:     str = os.getenv("PG1_PORT", "")
    PG1_DATABASE: str = os.getenv("PG1_DATABASE", "")
    PG1_USERNAME: str = os.getenv("PG1_USERNAME", "")
    PG1_PASSWORD: str = os.getenv("PG1_PASSWORD", "")

    # LLM
    LLM_PROVIDER: str = get_nested_value(yaml_datas, ["llm", "provider"], "")

    # Openrouter
    OPENROUTER_API_KEY:  str = os.getenv("OPENROUTER_API_KEY", "")
    OPENROUTER_BASE_URL: str = get_nested_value(yaml_datas, ["openrouter", "base_url"], "")
    MODEL_NAME:          str = get_nested_value(yaml_datas, ["openrouter", "model_name"], "")

    # Logger
    LOGGER_LEVEL: int = int(os.getenv("LOGGER_LEVEL", 10))

    # Agent
    AGENT_MAX_TIMEOUT: float = get_nested_value(yaml_datas, ["agent", "max_timeout"], 1)  # 최대 응답 대기시간
    AGENT_MAX_RETRIES: int = get_nested_value(yaml_datas, ["agent", "max_retries"], 1)  # 최대 재시도 횟수


cfg = Config()


__all__ = ["cfg"]