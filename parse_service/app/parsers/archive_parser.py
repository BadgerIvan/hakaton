import gzip
import io
import json
import tarfile
import tempfile
import zipfile
from pathlib import Path,PurePosixPath
from .base import BaseParser,ParseResult

class ArchiveParser(BaseParser):
    extensions=('.zip','.tar','.gz','.tgz','.epub')
    def parse(self,path):
        from ..registry import discover
        from ..detection import choose,UnsupportedFormat
        registry=discover();data=path.read_bytes();entries=[];warnings=[]
        if zipfile.is_zipfile(io.BytesIO(data)):
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                infos=[x for x in z.infolist() if not x.is_dir()]
                if len(infos)>500 or sum(x.file_size for x in infos)>128*1024*1024:raise ValueError('Архив превышает лимит: 500 файлов / 128 MiB')
                if path.suffix.lower()=='.epub' or 'META-INF/container.xml' in z.namelist():
                    from lxml import etree
                    from posixpath import normpath,join,dirname
                    parser=etree.XMLParser(resolve_entities=False,no_network=True)
                    container=etree.fromstring(z.read('META-INF/container.xml'),parser)
                    opf=container.xpath('//*[local-name()="rootfile"]/@full-path')[0]
                    tree=etree.fromstring(z.read(opf),parser)
                    manifest={x.get('id'):normpath(join(dirname(opf),x.get('href',''))) for x in tree.xpath('//*[local-name()="manifest"]/*')}
                    names=[manifest[x] for x in tree.xpath('//*[local-name()="spine"]/*/@idref') if x in manifest]
                    entries=[(name,z.read(name)) for name in names]
                else:
                    warnings.extend("Зашифрованный файл пропущен: "+x.filename for x in infos if x.flag_bits&1)
                    entries=[(x.filename,z.read(x)) for x in infos if not x.flag_bits&1]
        elif tarfile.is_tarfile(path):
            with tarfile.open(path) as t:
                members=[m for m in t if m.isfile()]
                if len(members)>500 or sum(m.size for m in members)>128*1024*1024:raise ValueError('TAR превышает лимит 500 файлов / 128 MiB')
                entries=[(m.name,t.extractfile(m).read()) for m in members]
        elif data.startswith(b'\x1f\x8b'):
            with gzip.GzipFile(fileobj=io.BytesIO(data)) as g:body=g.read(128*1024*1024+1)
            if len(body)>128*1024*1024:raise ValueError('GZIP превышает 128 MiB')
            entries=[(path.stem,body)]
        else:raise ValueError('Не распознан архив')
        out=[]
        with tempfile.TemporaryDirectory() as tmp:
            for n,(name,body) in enumerate(entries):
                member=PurePosixPath(name.replace('\\','/'))
                if '..' in member.parts or member.is_absolute():warnings.append('Отклонён небезопасный путь: '+name);continue
                p=Path(tmp)/(str(n)+member.suffix);p.write_bytes(body)
                try:
                    fmt,parser=choose(p,registry)
                    if isinstance(parser,ArchiveParser):raise UnsupportedFormat('Вложенный архив пропущен; распакуйте отдельно')
                    result=parser.parse(p)
                    if not result.markdown.strip():raise ValueError('Нет текста')
                    out.append('## Файл: '+name+'\n\n'+result.markdown)
                    warnings.extend(f'{name}: {w}' for w in result.warnings)
                except Exception as e:warnings.append(f'{name}: {type(e).__name__}: {e}')
        if not out:raise ValueError('В архиве нет извлечённого текста: '+'; '.join(warnings[:5]))
        return ParseResult('\n\n'.join(out),title=path.stem,warnings=warnings)
