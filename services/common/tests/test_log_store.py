import json
import logging

import pytest

from partner_observability import configure_logging
from partner_observability.logs import read_recent_logs


def event(service, number, level='INFO', **extra):
    return {'timestamp': f'2026-11-22T10:00:{number:02d}.000+00:00',
            'service': service, 'level': level, 'event': 'http.request', **extra}


def write(path, entries):
    path.write_text(''.join(json.dumps(entry, ensure_ascii=False) + '\n' for entry in entries))


def test_merge_rotation_filters_and_limit(tmp_path):
    write(tmp_path/'auth.jsonl', [event('auth', 3), event('auth', 5, 'ERROR')])
    write(tmp_path/'backend.jsonl', [event('backend', 4, 'WARNING', request_id='trace-Курс')])
    write(tmp_path/'backend.jsonl.1', [event('backend', 1, 'ERROR')])
    write(tmp_path/'rag.jsonl', [event('rag', 2, 'ERROR')])
    payload = read_recent_logs(tmp_path, limit=3)
    assert [row['service'] for row in payload['entries']] == ['auth', 'backend', 'auth']
    assert payload['truncated'] and payload['configured']
    payload = read_recent_logs(tmp_path, service='backend', level='WARNING', search='курс')
    assert [row['request_id'] for row in payload['entries']] == ['trace-Курс']
    assert len(read_recent_logs(tmp_path, level='ERROR')['entries']) == 3


def test_bad_lines_and_incomplete_writes_are_ignored(tmp_path):
    path = tmp_path/'auth.jsonl'
    write(path, [event('auth', 1), event('rag', 2), {'level': 'INFO'}, 42])
    with path.open('ab') as stream:
        stream.write(b'not json\n{"unfinished":')
    assert read_recent_logs(tmp_path)['entries'] == [event('auth', 1)]


def test_disabled_or_empty_store_does_not_invent_logs(tmp_path):
    assert read_recent_logs(None)['configured'] is False
    assert read_recent_logs(None)['entries'] == []
    assert read_recent_logs(tmp_path)['configured'] is True
    assert read_recent_logs(tmp_path)['entries'] == []


@pytest.mark.parametrize('service', ['../private', '/etc/passwd', 'frontend'])
def test_only_fixed_service_filenames_are_read(tmp_path, service):
    with pytest.raises(ValueError):
        read_recent_logs(tmp_path, service=service)


def test_long_files_are_read_from_a_bounded_tail(tmp_path, monkeypatch):
    import partner_observability.logs as store
    monkeypatch.setattr(store, 'READ_BYTES_PER_FILE', 256)
    write(tmp_path/'auth.jsonl', [event('auth', n) for n in range(30)])
    payload = read_recent_logs(tmp_path)
    assert payload['truncated']
    assert 0 < len(payload['entries']) < 30
    assert payload['entries'][0] == event('auth', 29)


def test_file_handler_redacts_rotates_and_does_not_duplicate(tmp_path, monkeypatch):
    monkeypatch.setenv('LOG_DIR', str(tmp_path))
    root = logging.getLogger()
    old_level = root.level
    old_handlers = list(root.handlers)
    try:
        configure_logging('auth')
        configure_logging('auth')
        handlers = [handler for handler in root.handlers if getattr(handler, '_partner_logging', False) and hasattr(handler, 'baseFilename')]
        assert len(handlers) == 1
        handlers[0].maxBytes = 420
        for n in range(12):
            logging.getLogger('partner.test').warning('operation password=private-token', extra={'status': 401})
        for handler in handlers:
            handler.flush()
        assert (tmp_path/'auth.jsonl.1').exists()
        assert len(list(tmp_path.glob('auth.jsonl*'))) <= 3
        content = ''.join(path.read_text() for path in tmp_path.glob('auth.jsonl*'))
        assert 'private-token' not in content and '[REDACTED]' in content
        assert read_recent_logs(tmp_path)['entries']
    finally:
        for handler in list(root.handlers):
            if handler not in old_handlers:
                root.removeHandler(handler)
                handler.close()
        for handler in old_handlers:
            if handler not in root.handlers:
                root.addHandler(handler)
        root.setLevel(old_level)
