import hashlib
import json


class RagProtocolError(Exception):
    pass


def normalize_sources(value):
    if not isinstance(value, list):
        raise RagProtocolError('Invalid sources')
    result = []
    for source in value:
        if not isinstance(source, dict) or not isinstance(source.get('source'), str):
            raise RagProtocolError('Invalid source')
        item = {key: source[key] for key in ('source', 'score', 'page', 'url') if key in source}
        item['doc_id'] = str(source.get('doc_id') or hashlib.sha256(source['source'].encode()).hexdigest()[:24])
        result.append(item)
    return result


async def read_events(response):
    name, data, size = 'message', [], 0
    async for line in response.aiter_lines():
        size += len(line)
        if size > 1_000_000:
            raise RagProtocolError('SSE event too large')
        if not line:
            if data:
                try:
                    yield name, json.loads('\n'.join(data))
                except ValueError:
                    raise RagProtocolError('Invalid SSE JSON') from None
            name, data, size = 'message', [], 0
        elif not line.startswith(':'):
            field, _, value = line.partition(':')
            if value.startswith(' '):
                value = value[1:]
            if field == 'event':
                name = value
            elif field == 'data':
                data.append(value)
    # The caller requires a complete `done` event, never EOF, to commit success.


def event(name, data):
    return f'event: {name}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n'
