"""Durable process-local append-only audit events, never credential storage."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import threading
import time
import uuid


def sanitize(value):
    secrets = [v for k, v in os.environ.items() if v and
               (any(marker in k.upper() for marker in ('API_KEY', 'PASSWORD', 'SECRET')) or
                k.upper() == 'TOKEN' or (k.upper().endswith('_TOKEN') and not k.upper().endswith('_PER_TOKEN')))]
    if isinstance(value, dict):
        return {str(k): '[REDACTED]' if re.search(r'authorization|api[_-]?key|password|secret|\.env', str(k), re.I)
                else sanitize(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [sanitize(v) for v in value]
    if isinstance(value, Path):
        value = str(value)
    if isinstance(value, str):
        for secret in sorted(secrets, key=len, reverse=True):
            value = value.replace(secret, '[REDACTED]')
        return re.sub(r'(?i)Bearer\s+[^\s"\']+', 'Bearer [REDACTED]', value)
    return value


class EventLedger:
    def __init__(self, root, attempt):
        self.root = Path(root)
        self.attempt = attempt
        self._nonce = uuid.uuid4().hex
        self._lock = threading.Lock()

    @property
    def path(self):
        # PID evaluated at append time: inherited objects after fork never share a file.
        return self.root / f'events-{os.getpid()}-{self._nonce}.jsonl'

    def append(self, kind, **fields):
        event = sanitize(dict(fields, kind=kind, attempt=self.attempt, pid=os.getpid(),
                              wall_timestamp=datetime.now(timezone.utc).isoformat(),
                              monotonic=time.monotonic(), event_id=uuid.uuid4().hex))
        data = (json.dumps(event, sort_keys=True, allow_nan=False) + '\n').encode()
        self.root.mkdir(parents=True, exist_ok=True)
        with self._lock:
            fd = os.open(self.path, os.O_CREAT | os.O_APPEND | os.O_WRONLY, 0o600)
            try:
                view = memoryview(data)
                while view:
                    view = view[os.write(fd, view):]
                os.fsync(fd)
            finally:
                os.close(fd)
        return event

    @classmethod
    def from_env(cls):
        root = os.environ.get('ACE_RTL_EVENT_ROOT')
        return cls(root, os.environ.get('ACE_RTL_ATTEMPT_ID', os.environ.get('ACE_RTL_ATTEMPT', 'unknown'))) if root else None


def durable_json(path, value):
    """Atomic complete publication, including fsync of data and directory."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        fd = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(value, stream, sort_keys=True, allow_nan=False)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    finally:
        temporary.unlink(missing_ok=True)
