"""Explicit experiment configuration; never infer credentials or endpoints."""
from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]


def load_config(path: str | Path | None = None) -> None:
    load_dotenv(path or ROOT / '.env.local', override=False)


def require(names: tuple[str, ...]) -> dict[str, str]:
    missing = [key for key in names if not os.environ.get(key, '').strip()]
    if missing:
        raise ValueError('Missing environment variables: ' + ', '.join(missing))
    return {key: os.environ[key].strip() for key in names}


def validate_url(value: str, name: str) -> str:
    parsed = urlsplit(value)
    if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError(f'{name} must be an HTTP(S) URL without embedded credentials, query or fragment')
    return value.rstrip('/')


def require_primary() -> dict[str, str]:
    config = require(('LLM_BASE_URL', 'LLM_API_KEY', 'LLM_MODEL'))
    validate_url(config['LLM_BASE_URL'], 'LLM_BASE_URL')
    return config


def require_jev() -> dict[str, str]:
    config = require(('JEV_API_MODE', 'JEV_ENDPOINT_URL', 'JEV_MODEL', 'JEV_AUTH_MODE'))
    if config['JEV_API_MODE'] != 'systemone':
        raise ValueError('JEV_API_MODE must be systemone; chat compatibility is not assumed')
    if config['JEV_AUTH_MODE'] == 'bearer':
        config.update(require(('JEV_API_KEY',)))
    elif config['JEV_AUTH_MODE'] != 'none':
        raise ValueError('JEV_AUTH_MODE must be none or bearer')
    validate_url(config['JEV_ENDPOINT_URL'], 'JEV_ENDPOINT_URL')
    return config


def positive_number(name: str, default: float) -> float:
    try:
        value = float(os.environ.get(name, default))
    except ValueError:
        raise ValueError(f'{name} must be a positive number') from None
    if not 0 < value < float('inf'):
        raise ValueError(f'{name} must be a finite positive number')
    return value
