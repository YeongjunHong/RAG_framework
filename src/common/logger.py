# settings/logging_config.py
# - ./settings/.env 에서 logger_level 값을 읽어 로깅 레벨을 설정

import logging

from settings.config import cfg


def _to_level(level_str: str|None=None) -> int:
    if not level_str:
        return logging.INFO
    s = level_str.strip().upper()
    return {
        "CRITICAL": logging.CRITICAL,
        "ERROR": logging.ERROR,
        "WARNING": logging.WARNING,
        "WARN": logging.WARNING,
        "INFO": logging.INFO,
        "DEBUG": logging.DEBUG,
        "NOTSET": logging.NOTSET,
    }.get(s, logging.INFO)


def get_logger(name: str, level: int|str=cfg.LOGGER_LEVEL) -> logging.Logger:
    if isinstance(level, str):
        level = _to_level(level)
    
    # 이미 핸들러가 구성된 경우 중복 구성 방지
    root = logging.getLogger()
    if not root.handlers:
        logging.basicConfig(
            level=level,
            format="%(asctime)s %(levelname)s %(name)s - %(message)s",
        )
    else:
        root.setLevel(level)
    return logging.getLogger(name)