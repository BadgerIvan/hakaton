"""JSON diagnostics shared by the three HTTP services. No request bodies or secrets."""
import contextvars
import json
import logging
import os
import re
import sys
import time
import traceback
from datetime import datetime, timezone
from uuid import uuid4

_request_id = contextvars.ContextVar('request_id', default='-')
_VALID_ID = re.compile(r'^[a-zA-Z0-9._-]{1,64}$')
_FIELDS = ('method', 'path', 'status', 'duration_ms', 'bytes_sent', 'outcome',
           'generation_id', 'conversation_id', 'replayed', 'chunks', 'files',
           'answer_chars', 'sources_count', 'phase', 'elapsed_ms')
_SECRET = re.compile(r'(?i)(password|authorization|cookie|csrf[_-]?token|admin[_-]?token|token)([\s"\x27]*[:=][\s"\x27]*)([^\s,;"\x27]+)')


def request_id():
    return _request_id.get()


def correlation_id(value):
    return value if isinstance(value, str) and _VALID_ID.fullmatch(value) else uuid4().hex


class JsonFormatter(logging.Formatter):
    def __init__(self, service):
        super().__init__()
        self.service = service

    def format(self, record):
        message = _SECRET.sub(r'\1\2[REDACTED]', record.getMessage())
        payload = {'timestamp': datetime.fromtimestamp(record.created, timezone.utc).isoformat(timespec='milliseconds'),
                   'level': record.levelname, 'service': self.service,
                   'logger': record.name, 'request_id': request_id(), 'event': message}
        payload.update({key: getattr(record, key) for key in _FIELDS if hasattr(record, key)})
        if record.exc_info and record.exc_info[0]:
            # Exception values can contain prompts, SQL parameters and credentials.
            # Frames and exception class locate the failure without exposing those values.
            payload['error'] = {'type': record.exc_info[0].__name__, 'frames': [
                {'file': frame.filename, 'line': frame.lineno, 'function': frame.name}
                for frame in traceback.extract_tb(record.exc_info[2])[-12:]]}
        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_logging(service):
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter(service))
    root = logging.getLogger()
    # Only replace our handler; pytest/caller handlers must keep working.
    for old in list(root.handlers):
        if getattr(old, '_partner_logging', False):
            root.removeHandler(old)
    handler._partner_logging = True
    root.addHandler(handler)
    root.setLevel(getattr(logging, os.getenv('LOG_LEVEL', 'INFO').upper(), logging.INFO))
    for name in ('httpx', 'httpcore', 'ollama', 'multipart', 'python_multipart', 'sqlalchemy.engine'):
        logging.getLogger(name).setLevel(logging.WARNING)
    for name in ('uvicorn', 'uvicorn.error', 'uvicorn.access'):
        logger = logging.getLogger(name)
        logger.handlers.clear()
        logger.propagate = True
    logging.getLogger('uvicorn.access').disabled = True


async def propagate_request_id(request):
    """httpx request event hook; applies to auth, RAG, Ollama HTTP calls."""
    if request_id() != '-':
        request.headers['X-Request-ID'] = request_id()


class RequestLogMiddleware:
    """Pure ASGI: measure the full SSE lifetime, including disconnects."""
    def __init__(self, app):
        self.app = app
        self.log = logging.getLogger('partner.http')

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        headers = dict(scope.get('headers', []))
        identity = correlation_id(headers.get(b'x-request-id', b'').decode('latin-1'))
        token = _request_id.set(identity)
        start, status, sent, outcome = time.monotonic(), 500, 0, 'complete'
        started = False

        async def send_logged(message):
            nonlocal status, sent, started
            if message['type'] == 'http.response.start':
                started = True
                status = message['status']
                new_headers = [(k, v) for k, v in message.get('headers', []) if k.lower() != b'x-request-id']
                new_headers.append((b'x-request-id', identity.encode('ascii')))
                message = {**message, 'headers': new_headers}
            elif message['type'] == 'http.response.body':
                sent += len(message.get('body', b''))
            await send(message)

        try:
            await self.app(scope, receive, send_logged)
        except BaseException as exc:
            outcome = 'cancelled' if type(exc).__name__ == 'CancelledError' else 'failed'
            if isinstance(exc, Exception):
                self.log.error('http.exception', exc_info=True)
                if not started:
                    body = json.dumps({'detail': 'Внутренняя ошибка сервиса'}, ensure_ascii=False).encode()
                    await send_logged({'type': 'http.response.start', 'status': 500, 'headers': [(b'content-type', b'application/json; charset=utf-8'), (b'cache-control', b'no-store')]})
                    await send_logged({'type': 'http.response.body', 'body': body})
                    return
            raise
        finally:
            # The route template avoids logging identifiers/query strings in URLs.
            route = scope.get('route')
            path = getattr(route, 'path', None) or ('/health' if scope.get('path') == '/health' else '<unmatched>')
            level = logging.ERROR if status >= 500 else logging.WARNING if status >= 400 else logging.INFO
            if path == '/health' and status < 400:
                level = logging.DEBUG
            self.log.log(level, 'http.request', extra={'method': scope['method'], 'path': path,
                'status': status, 'duration_ms': round((time.monotonic() - start) * 1000, 2),
                'bytes_sent': sent, 'outcome': outcome})
            _request_id.reset(token)
