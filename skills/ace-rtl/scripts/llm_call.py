#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Role-scoped chat-completions caller for ACE-RTL."""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

from ace_rtl_agent.llm_backend import (
    DEFAULT_MODEL_ALIAS,
    LLMBackend,
    get_model_max_output_tokens,
    is_nvidia_inference_model,
    resolve_model_name,
)


def resolve_model(model: str) -> str:
    return resolve_model_name(model or DEFAULT_MODEL_ALIAS)


def default_max_tokens(model: str) -> int:
    return get_model_max_output_tokens(model)


def choose_provider(provider: str, model: str) -> str:
    if provider != "auto":
        return provider
    return "nvidia" if is_nvidia_inference_model(model) else "openai"


def load_messages(args: argparse.Namespace) -> List[Dict[str, str]]:
    if args.messages_file:
        payload = json.loads(Path(args.messages_file).read_text(encoding="utf-8"))
        messages = payload.get("messages", payload) if isinstance(payload, dict) else payload
        if not isinstance(messages, list):
            raise ValueError("messages file must contain a list or an object with a messages list")
        return messages

    prompt = Path(args.prompt_file).read_text(encoding="utf-8") if args.prompt_file else sys.stdin.read()
    if not prompt.strip():
        raise ValueError("empty prompt")

    messages: List[Dict[str, str]] = []
    if args.system:
        messages.append({"role": "system", "content": args.system})
    messages.append({"role": "user", "content": prompt})
    return messages


def shrink_last_user(messages: List[Dict[str, str]], max_chars: int) -> List[Dict[str, str]]:
    copied = [dict(m) for m in messages]
    marker = "\n\n... [PROMPT TRUNCATED AFTER CONTEXT REJECTION] ...\n\n"
    for msg in reversed(copied):
        if msg.get("role") != "user":
            continue
        content = msg.get("content") or ""
        if len(content) <= max_chars:
            return copied
        keep = max(1000, max_chars - len(marker))
        head = int(keep * 0.6)
        tail = keep - head
        msg["content"] = content[:head] + marker + content[-tail:]
        return copied
    return copied


def transient_error(error: Exception) -> bool:
    text = str(error).lower()
    return any(
        token in text
        for token in [
            "timeout",
            "timed out",
            "429",
            "500",
            "502",
            "503",
            "504",
            "529",
            "connection reset",
            "connection error",
            "temporarily unavailable",
            "rate limit",
            "too many requests",
            "empty response",
            "overloaded",
            "limit reached",
            "context window",
            "contextwindow",
            "maximum context",
            "too many tokens",
        ]
    )


def context_error(error: Exception) -> bool:
    text = str(error).lower()
    return any(token in text for token in ["context window", "contextwindow", "maximum context", "too many tokens"])


def call_with_retries(
    *,
    provider: str,
    model: str,
    messages: List[Dict[str, str]],
    temperature: float,
    max_tokens: int,
    max_retries: int,
    initial_backoff: float,
    shrink_chars: int,
) -> Dict[str, object]:
    backend = LLMBackend(model=model, provider=provider)
    working_messages = messages
    context_shrink_used = False
    backoff = initial_backoff
    last_error: Optional[Exception] = None

    for attempt in range(max_retries + 1):
        try:
            result = backend.complete_messages(
                working_messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            result["attempts"] = attempt + 1
            return result
        except Exception as exc:
            last_error = exc
            if context_error(exc) and not context_shrink_used and attempt < max_retries:
                context_shrink_used = True
                working_messages = shrink_last_user(working_messages, shrink_chars)
                continue
            if "non_retryable" in str(exc).lower():
                break
            if attempt >= max_retries or not transient_error(exc):
                break
            wait = min(backoff, 60.0) * random.uniform(0.8, 1.2)
            print(f"warning: transient LLM error: {exc}; retrying in {wait:.1f}s", file=sys.stderr)
            time.sleep(wait)
            backoff = min(backoff * 2, 60.0)

    raise RuntimeError(f"LLM call failed after {max_retries + 1} attempts: {last_error}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Call an ACE-RTL role model")
    parser.add_argument("--component", required=True, choices=["generator", "reflector", "coordinator"])
    parser.add_argument("--model", default=DEFAULT_MODEL_ALIAS, help="Model alias or provider model id")
    parser.add_argument("--provider", choices=["auto", "nvidia", "openai"], default="auto")
    parser.add_argument("--system")
    parser.add_argument("--prompt-file")
    parser.add_argument("--messages-file")
    parser.add_argument("--output", required=True)
    parser.add_argument("--temperature", type=float, default=0.2)
    parser.add_argument("--max-tokens", type=int, default=0)
    parser.add_argument("--timeout", type=int, default=1800)
    parser.add_argument("--max-retries", type=int, default=3)
    parser.add_argument("--initial-backoff", type=float, default=5.0)
    parser.add_argument("--context-retry-chars", type=int, default=120000)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    model = resolve_model(args.model)
    provider = choose_provider(args.provider, model)
    if provider == "nvidia":
        os.environ.setdefault("NEMOTRON_TIMEOUT", str(args.timeout))
    else:
        os.environ.setdefault("OPENAI_TIMEOUT", str(args.timeout))
    max_tokens = args.max_tokens or default_max_tokens(model)
    messages = load_messages(args)
    result = call_with_retries(
        provider=provider,
        model=model,
        messages=messages,
        temperature=args.temperature,
        max_tokens=max_tokens,
        max_retries=args.max_retries,
        initial_backoff=args.initial_backoff,
        shrink_chars=args.context_retry_chars,
    )
    result["component"] = args.component
    Path(args.output).write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"wrote {args.component} response from {provider}:{model} to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
