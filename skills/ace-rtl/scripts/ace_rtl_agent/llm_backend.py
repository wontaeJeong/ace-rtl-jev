# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""NVIDIA Inference/custom LLM backend for ACE-RTL."""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import sys
from typing import Any, Dict, List, Optional


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DEFAULT_MODEL_ALIAS = "nvidia/nemotron-3-ultra-550b-a55b"
DEFAULT_MODEL_ID = DEFAULT_MODEL_ALIAS
DEFAULT_NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"

MODEL_CONTEXT_TOKENS = {
    "nvidia/nemotron-3-ultra": 262144,
    "nemotron": 262144,
}
DEFAULT_CONTEXT_TOKENS = 128000
DEFAULT_MAX_OUTPUT_TOKENS = 32768
DEFAULT_REASONING_BUDGET = 32768
RESPONSE_TOKEN_RESERVE = 40000
CHARS_PER_TOKEN = float(os.getenv("ACE_RTL_PROMPT_CHARS_PER_TOKEN", "0.75"))


def resolve_model_name(model_name: str) -> str:
    """Resolve an empty model name to the configured ACE-RTL default."""
    return (model_name or os.environ.get("ACE_RTL_MODEL") or DEFAULT_MODEL_ALIAS).strip()


def env_flag(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() not in {"0", "false", "no", "off", ""}


def streaming_enabled() -> bool:
    return env_flag("ACE_RTL_STREAM", True)


def reasoning_enabled() -> bool:
    return env_flag("ACE_RTL_ENABLE_REASONING", True)


def env_positive_int(name: str, default: int) -> int:
    value = os.environ.get(name)
    if value is None:
        return default
    try:
        parsed = int(value)
    except ValueError:
        return default
    return parsed if parsed > 0 else default


def nvidia_base_url() -> str:
    return (
        os.environ.get("NVIDIA_BASE_URL")
        or os.environ.get("NVIDIA_INFERENCE_BASE_URL")
        or os.environ.get("ACE_RTL_BASE_URL")
        or DEFAULT_NVIDIA_BASE_URL
    ).rstrip("/")


def nvidia_api_key() -> Optional[str]:
    return os.environ.get("NVIDIA_API_KEY")


def custom_script_path() -> Optional[str]:
    value = os.environ.get("ACE_RTL_LLM_SCRIPT")
    return value.strip() if value and value.strip() else None


def custom_script_configured() -> bool:
    return bool(custom_script_path())


def get_model_context_tokens(model_name: str) -> int:
    low = (model_name or "").lower()
    for key, tokens in MODEL_CONTEXT_TOKENS.items():
        if key in low:
            return tokens
    return env_positive_int("ACE_RTL_CONTEXT_TOKENS", DEFAULT_CONTEXT_TOKENS)


def get_model_max_output_tokens(model_name: str) -> int:
    del model_name
    fallback = env_positive_int("NEMOTRON_MAX_TOKENS", DEFAULT_MAX_OUTPUT_TOKENS)
    return env_positive_int("ACE_RTL_MAX_TOKENS", fallback)


def get_reasoning_budget(max_tokens: int) -> int:
    default_budget = min(DEFAULT_REASONING_BUDGET, max_tokens)
    fallback = env_positive_int("NEMOTRON_REASONING_BUDGET", default_budget)
    return env_positive_int("ACE_RTL_REASONING_BUDGET", fallback)


def enforce_prompt_char_budget(prompt: str, model_name: str, logger_obj=None) -> str:
    """Bound a prompt to the configured model context window with middle truncation."""
    context_tokens = get_model_context_tokens(model_name)
    input_token_budget = max(1000, context_tokens - RESPONSE_TOKEN_RESERVE)
    max_chars = int(input_token_budget * CHARS_PER_TOKEN)

    if len(prompt) <= max_chars:
        return prompt

    marker = "\n\n... [PROMPT TRUNCATED to fit model context window] ...\n\n"
    keep = max(1000, max_chars - len(marker))
    head_chars = int(keep * 0.6)
    tail_chars = keep - head_chars
    truncated = prompt[:head_chars] + marker + prompt[-tail_chars:]
    if logger_obj:
        logger_obj.warning(
            "Prompt (%s chars) exceeds context budget for %s; truncated to %s chars.",
            len(prompt),
            model_name,
            len(truncated),
        )
    return truncated


def message_content_to_text(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: List[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                value = item.get("text")
                if value is None:
                    value = item.get("content")
                if isinstance(value, dict):
                    value = value.get("text") or value.get("content")
                if value is not None:
                    parts.append(str(value))
        return "\n".join(parts)
    return str(content)


def message_to_text(message: Any) -> str:
    if message is None:
        return ""
    if isinstance(message, dict):
        return message_content_to_text(message.get("content"))
    return message_content_to_text(getattr(message, "content", None))


def strip_visible_reasoning_tags(text: str) -> str:
    cleaned = re.sub(r"(?is)<think\b[^>]*>.*?</think>\s*", "", text)
    cleaned = re.sub(r"(?is)^.*?</think>\s*", "", cleaned)
    return cleaned


def _obj_get(obj: Any, name: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _model_dump(obj: Any) -> Dict[str, Any]:
    if isinstance(obj, dict):
        return obj
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if hasattr(obj, "dict"):
        return obj.dict()
    return {"raw": str(obj)}


def validate_nvidia_api_key(api_key: Optional[str] = None) -> Dict[str, Any]:
    key = api_key or nvidia_api_key()
    if not key and not custom_script_configured():
        return {"valid": False, "message": "NVIDIA_API_KEY is not set"}
    return {"valid": True, "message": "LLM credentials or custom adapter are configured"}


def check_model_availability(model_name: str, api_key: Optional[str] = None) -> Dict[str, Any]:
    resolved = resolve_model_name(model_name)
    key = api_key or nvidia_api_key()
    if not key and not custom_script_configured():
        return {
            "available": False,
            "model_id": resolved,
            "message": "NVIDIA_API_KEY is not set",
        }
    return {"available": True, "model_id": resolved, "message": "Configured"}



class LLMBackend:
    """LLM backend for NVIDIA Inference API or a user-provided adapter script."""

    def __init__(self, model: str = DEFAULT_MODEL_ALIAS, provider: str = "auto"):
        self.model = resolve_model_name(model)
        self.provider = self._resolve_provider(provider)
        self.client = self._provider_client(self.provider)
        logger.info("Initialized LLM backend provider=%s model=%s", self.provider, self.model)

    @staticmethod
    def _resolve_provider(provider: str) -> str:
        if provider == "auto":
            return "custom" if custom_script_configured() else "nvidia"
        if provider not in {"nvidia", "custom"}:
            raise ValueError(f"unsupported LLM provider: {provider}")
        return provider

    @staticmethod
    def _provider_client(provider: str) -> Any:
        if provider == "custom":
            if not custom_script_configured():
                raise ValueError("ACE_RTL_LLM_SCRIPT must be set for custom LLM provider")
            return None
        key = nvidia_api_key()
        if not key:
            raise ValueError("NVIDIA_API_KEY must be set for NVIDIA Inference API calls")
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError("Install the openai Python package to use NVIDIA Inference API") from exc
        return OpenAI(base_url=nvidia_base_url(), api_key=key)

    def _request_timeout(self) -> int:
        return env_positive_int(
            "ACE_RTL_LLM_TIMEOUT",
            env_positive_int("NVIDIA_TIMEOUT", 1800),
        )

    def _extra_body(self, max_tokens: int) -> Dict[str, Any]:
        if not reasoning_enabled():
            return {"chat_template_kwargs": {"enable_thinking": False}}
        return {
            "chat_template_kwargs": {"enable_thinking": True},
            "reasoning_budget": get_reasoning_budget(max_tokens),
        }

    def _complete_with_custom_script(
        self,
        messages: List[Dict[str, str]],
        temperature: float,
        top_p: float,
        max_tokens: int,
    ) -> Dict[str, Any]:
        script = custom_script_path()
        if not script:
            raise ValueError("ACE_RTL_LLM_SCRIPT must be set for custom LLM provider")
        cmd = [script]
        if script.endswith(".py") and not os.access(script, os.X_OK):
            cmd = [sys.executable, script]
        request = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "top_p": top_p,
            "max_tokens": max_tokens,
            "stream": streaming_enabled(),
            "extra_body": self._extra_body(max_tokens),
        }
        proc = subprocess.run(
            cmd,
            input=json.dumps(request),
            text=True,
            capture_output=True,
            timeout=self._request_timeout(),
        )
        if proc.returncode != 0:
            detail = (proc.stderr or proc.stdout or "").strip()[:1200]
            raise RuntimeError(f"custom LLM script exited {proc.returncode}: {detail}")
        output = proc.stdout.strip()
        if not output:
            raise ValueError("custom LLM script returned empty output")
        try:
            payload = json.loads(output)
        except json.JSONDecodeError:
            content = output
        else:
            if isinstance(payload, dict) and payload.get("choices"):
                return payload
            if isinstance(payload, dict) and "content" in payload:
                content = message_content_to_text(payload.get("content"))
            else:
                content = json.dumps(payload)
        return {
            "model": self.model,
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": content},
                    "finish_reason": "stop",
                }
            ],
            "custom": True,
        }

    def _stream_nvidia_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float,
        top_p: float,
        max_tokens: int,
    ) -> Dict[str, Any]:
        completion = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
            extra_body=self._extra_body(max_tokens),
            stream=True,
            timeout=self._request_timeout(),
        )
        content_parts: List[str] = []
        reasoning_parts: List[str] = []
        finish_reason = None
        response_model = self.model
        response_id = None

        for chunk in completion:
            response_id = _obj_get(chunk, "id", response_id)
            response_model = _obj_get(chunk, "model", response_model)
            choices = _obj_get(chunk, "choices", []) or []
            if not choices:
                continue
            choice = choices[0]
            finish_reason = _obj_get(choice, "finish_reason", finish_reason)
            delta = _obj_get(choice, "delta", {})
            reasoning = _obj_get(delta, "reasoning_content")
            content = _obj_get(delta, "content")
            if reasoning:
                reasoning_parts.append(str(reasoning))
            if content is not None:
                content_parts.append(str(content))

        return {
            "id": response_id,
            "model": response_model,
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": "".join(content_parts),
                        "reasoning_content": "".join(reasoning_parts),
                    },
                    "finish_reason": finish_reason,
                }
            ],
            "stream": True,
        }

    def _nonstream_nvidia_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float,
        top_p: float,
        max_tokens: int,
    ) -> Dict[str, Any]:
        completion = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
            extra_body=self._extra_body(max_tokens),
            stream=False,
            timeout=self._request_timeout(),
        )
        return _model_dump(completion)

    def _complete_messages(
        self,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: Optional[int] = None,
        top_p: Optional[float] = None,
    ) -> Dict[str, Any]:
        if max_tokens is None:
            max_tokens = get_model_max_output_tokens(self.model)
        if top_p is None:
            top_p = float(os.getenv("ACE_RTL_TOP_P", "0.95"))

        if self.provider == "custom":
            return self._complete_with_custom_script(messages, temperature, top_p, max_tokens)
        if streaming_enabled():
            payload = self._stream_nvidia_completion(messages, temperature, top_p, max_tokens)
        else:
            payload = self._nonstream_nvidia_completion(messages, temperature, top_p, max_tokens)

        if not payload.get("choices"):
            raise ValueError("Response contained no choices")
        return payload

    def _content_from_payload(self, payload: Dict[str, Any], max_tokens: int) -> str:
        choice = payload["choices"][0]
        message = choice.get("message", {})
        content = strip_visible_reasoning_tags(message_to_text(message))
        finish = choice.get("finish_reason")
        logger.info("%s finish_reason=%s", self.provider, finish)

        if not content.strip():
            reasoning = message_content_to_text(message.get("reasoning_content") or message.get("reasoning"))
            logger.warning(
                "Empty content from %s (finish_reason=%s, max_tokens=%s, reasoning_content_len=%s).",
                self.model,
                finish,
                max_tokens,
                len(reasoning) if reasoning else 0,
            )
            if finish == "length":
                raise ValueError(
                    "NON_RETRYABLE: empty content - model exhausted token "
                    f"budget on reasoning (finish_reason=length, max_tokens={max_tokens})"
                )
            raise ValueError("Empty response from LLM API")
        return content

    def _get_model_response(
        self,
        prompt: str,
        temperature: float,
        max_tokens: Optional[int] = None,
    ) -> str:
        if max_tokens is None:
            max_tokens = get_model_max_output_tokens(self.model)
        payload = self._complete_messages(
            [{"role": "user", "content": prompt}],
            temperature,
            max_tokens,
        )
        return self._content_from_payload(payload, max_tokens)

    def complete_messages(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> Dict[str, Any]:
        if temperature is None:
            temperature = float(os.getenv("ACE_RTL_TEMPERATURE", "0.2"))
        if max_tokens is None:
            max_tokens = get_model_max_output_tokens(self.model)
        payload = self._complete_messages(messages, temperature, max_tokens)
        content = self._content_from_payload(payload, max_tokens)
        choice = payload["choices"][0]
        finish = choice.get("finish_reason")
        return {
            "provider": self.provider,
            "model": self.model,
            "content": content,
            "finish_reason": finish,
            "truncated": finish == "length",
            "raw": payload,
            "attempts": 1,
        }

    def prompt(
        self,
        prompt: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        if temperature is None:
            temperature = float(os.getenv("ACE_RTL_TEMPERATURE", "0.2"))
        prompt = enforce_prompt_char_budget(prompt, self.model, logger)
        return self._get_model_response(prompt, temperature, max_tokens=max_tokens)


LLMInstance = LLMBackend
