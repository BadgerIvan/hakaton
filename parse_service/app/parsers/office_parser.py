import io
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path
from .base import BaseParser,ParseResult
from .structured_parser import table

class SpreadsheetParser(BaseParser):
    extensions=('.xlsx','.xlsm','.xls')
    def parse(self,path):
        from ..detection import detect
        fmt=detect(path);out=[]
        if fmt=='.xls':
            import xlrd
            book=xlrd.open_workbook(path)
            for sheet in book.sheets():out.append('## '+sheet.name+'\n\n'+table(sheet.row_values(n) for n in range(sheet.nrows)))
        else:
            import openpyxl
            with path.open('rb') as stream:
                book=openpyxl.load_workbook(stream,read_only=True,data_only=False)
                try:
                    for sheet in book:out.append('## '+sheet.title+'\n\n'+table(sheet.values))
                finally:book.close()
        return ParseResult('\n\n'.join(out),title=path.stem)

class PresentationParser(BaseParser):
    extensions=('.pptx',)
    def parse(self,path):
        from pptx import Presentation
        slides=Presentation(io.BytesIO(path.read_bytes()));out=[]
        for n,slide in enumerate(slides.slides,1):
            lines=[f'## Слайд {n}']
            def shapes(items):
                for shape in items:
                    if hasattr(shape,'shapes'):yield from shapes(shape.shapes)
                    elif shape.has_table:yield table([[c.text for c in r.cells] for r in shape.table.rows])
                    elif shape.has_text_frame:yield shape.text
            lines.extend(shapes(slide.shapes))
            if slide.has_notes_slide:lines.extend(['### Заметки',slide.notes_slide.notes_text_frame.text])
            out.append('\n\n'.join(lines))
        return ParseResult('\n\n'.join(out),title=path.stem,pages=len(slides.slides))

class OpenDocumentParser(BaseParser):
    extensions=('.odt','.ods')
    def parse(self,path):
        from lxml import etree
        with zipfile.ZipFile(path) as z:
            info=z.getinfo('content.xml')
            if info.file_size>32*1024*1024:raise ValueError('content.xml превышает 32 MiB')
            root=etree.fromstring(z.read(info),etree.XMLParser(resolve_entities=False,no_network=True))
        ns={'text':'urn:oasis:names:tc:opendocument:xmlns:text:1.0','table':'urn:oasis:names:tc:opendocument:xmlns:table:1.0'}
        lines=[]
        for node in root.xpath('//text:h|//text:p|//table:table',namespaces=ns):
            if node.xpath('ancestor::table:table',namespaces=ns):continue
            if node.tag.endswith('}table'):
                rows=[]
                for row in node.xpath('./table:table-row',namespaces=ns):
                    cells=[]
                    for cell in row:
                        repeat=min(int(cell.get('{'+ns['table']+'}number-columns-repeated','1')),1000)
                        cells.extend([' '.join(cell.itertext())]*repeat)
                    rows.append(cells)
                lines.append(table(rows))
            else:lines.append(('## ' if node.tag.endswith('}h') else '')+''.join(node.itertext()))
        return ParseResult('\n\n'.join(lines),title=path.stem)

class RTFParser(BaseParser):
    extensions=('.rtf',)
    def parse(self,path):
        from striprtf.striprtf import rtf_to_text
        return ParseResult(rtf_to_text(path.read_bytes().decode('latin1')),title=path.stem)

class LegacyOfficeParser(BaseParser):
    extensions=('.doc','.ppt')
    def parse(self,path):
        from ..detection import detect
        fmt=detect(path)
        if fmt=='.doc' and shutil.which('antiword'):
            p=subprocess.run(['antiword','-m','UTF-8.txt',str(path.resolve())],capture_output=True,timeout=90,check=True)
            return ParseResult(p.stdout.decode('utf-8'),title=path.stem)
        executable=shutil.which('libreoffice') or shutil.which('soffice')
        if not executable:raise RuntimeError('Для DOC нужен antiword или LibreOffice; для PPT — LibreOffice')
        with tempfile.TemporaryDirectory() as tmp:
            tmp=Path(tmp);local=tmp/('input'+fmt);local.write_bytes(path.read_bytes())
            dest=tmp/'converted';dest.mkdir()
            subprocess.run([executable,'-env:UserInstallation='+ (tmp/'profile').as_uri(),'--headless','--convert-to','docx' if fmt=='.doc' else 'pptx','--outdir',str(dest),str(local)],capture_output=True,timeout=120,check=True)
            files=list(dest.iterdir())
            if len(files)!=1:raise ValueError('LibreOffice не создал результат конвертации')
            if fmt=='.doc':
                from .docx_parser import DOCXParser
                return DOCXParser().parse(files[0])
            return PresentationParser().parse(files[0])
