"""Content-based dispatch, independent of the input directory."""
import io
import zipfile
import json
from pathlib import Path

class UnsupportedFormat(ValueError): pass

def detect(path):
    data=path.read_bytes()
    head=data[:8192].lstrip()
    suffix=path.suffix.lower()
    if data.startswith(b'%PDF'):return '.pdf'
    if data.startswith(b'PK') and zipfile.is_zipfile(io.BytesIO(data)):
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            names=z.namelist()
            if 'word/document.xml' in names:return '.docx'
            if 'xl/workbook.xml' in names:return '.xlsx'
            if 'ppt/presentation.xml' in names:return '.pptx'
            if 'mimetype' in names:
                mime=z.read('mimetype')
                if b'opendocument.text' in mime:return '.odt'
                if b'opendocument.spreadsheet' in mime:return '.ods'
                if b'epub+zip' in mime:return '.epub'
        return '.zip'
    if data.startswith(b'\xd0\xcf\x11\xe0'):
        if suffix in ('.doc','.xls','.ppt'):return suffix
        if b'W\x00o\x00r\x00d\x00D\x00o\x00c' in data:return '.doc'
        if b'W\x00o\x00r\x00k\x00b\x00o\x00o\x00k' in data:return '.xls'
        raise UnsupportedFormat('Контейнер OLE: укажите расширение .doc/.xls/.ppt')
    if data.startswith((b'\x89PNG',b'\xff\xd8\xff',b'GIF8',b'II*\x00',b'MM\x00*',b'BM')) or data[:4]==b'RIFF' and data[8:12]==b'WEBP':return '.image'
    if data.startswith(b'\x1f\x8b'):return '.gz'
    if len(data)>262 and data[257:262]==b'ustar':return '.tar'
    if head.startswith(b'{\\rtf'):return '.rtf'
    if b'\x00' in data[:8192] and not data.startswith((b'\xff\xfe',b'\xfe\xff')):
        raise UnsupportedFormat('Неизвестный бинарный формат; текст не извлечён')
    from charset_normalizer import from_bytes
    if data.startswith((b'\xff\xfe',b'\xfe\xff')):text=data.decode('utf-16')
    else:
        match=from_bytes(data).best()
        if match is None:raise UnsupportedFormat('Не удалось определить текстовую кодировку')
        text=str(match)
    if not text.strip():raise UnsupportedFormat('Пустой файл')
    if sum(c.isprintable() or c.isspace() for c in text)/len(text)<.95:
        raise UnsupportedFormat('Неизвестный бинарный формат; печатных символов недостаточно')
    lower=text[:8192].lstrip().lower()
    if '<html' in lower or '<!doctype html' in lower:return '.html'
    if lower.startswith(('{','[')):
        try:json.loads(text);return '.json'
        except ValueError:pass
    if suffix in ('.json','.csv','.tsv','.jsonl','.ndjson','.yaml','.yml','.xml','.svg','.html','.htm','.md','.markdown','.css','.js','.ts','.py','.sql','.log','.ini','.cfg','.toml','.rst'):
        return suffix
    if lower.startswith('<?xml'):return '.xml'
    return '.txt'

def choose(path,registry):
    fmt=detect(path)
    parser=registry.get(fmt)
    if parser is None:raise UnsupportedFormat(f'Нет парсера для {fmt}')
    return fmt,parser
