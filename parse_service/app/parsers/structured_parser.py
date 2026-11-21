import csv
import io
import json
from pathlib import Path
from .base import BaseParser,ParseResult

def read_text(path):
    data=path.read_bytes()
    if data.startswith((b'\xff\xfe',b'\xfe\xff')):return data.decode('utf-16')
    try:return data.decode('utf-8-sig')
    except UnicodeDecodeError:
        from charset_normalizer import from_bytes
        m=from_bytes(data).best()
        if m is None:raise ValueError('Не удалось определить кодировку')
        return str(m)

def table(rows):
    rows=list(rows)
    if not rows:return ''
    width=max(map(len,rows))
    def row(r):return '| '+' | '.join(str(x if x is not None else '').replace('|','\\|').replace('\n','<br>') for x in list(r)+['']*(width-len(r)))+' |'
    return '\n'.join([row(rows[0]),row(['---']*width)]+[row(r) for r in rows[1:]])

def render(value,level=2):
    if isinstance(value,dict):return '\n\n'.join('#'*min(level,6)+' '+str(k)+'\n\n'+render(v,level+1) for k,v in value.items())
    if isinstance(value,list):return '\n\n'.join(f'### Запись {n}\n\n'+render(v,level+1) for n,v in enumerate(value,1))
    return 'null' if value is None else str(value)

class StructuredParser(BaseParser):
    extensions=('.csv','.tsv','.jsonl','.ndjson','.yaml','.yml','.xml','.svg')
    def parse(self,path):
        text=read_text(path);ext=path.suffix.lower()
        if ext in ('.csv','.tsv'):
            try:dialect=csv.Sniffer().sniff(text[:8192],delimiters=',;\t|')
            except csv.Error:dialect=csv.excel_tab if ext=='.tsv' else csv.excel
            body=table(csv.reader(io.StringIO(text),dialect))
        elif ext in ('.jsonl','.ndjson'):body=render([json.loads(x) for x in text.splitlines() if x.strip()])
        elif ext in ('.yaml','.yml'):
            import yaml
            body=render(list(yaml.safe_load_all(text)))
        else:
            from lxml import etree
            tree=etree.fromstring(text.encode(),parser=etree.XMLParser(resolve_entities=False,no_network=True))
            def xml(node,depth=2):
                out=['#'*min(depth,6)+' '+str(node.tag)]
                if node.attrib:out.append(render(dict(node.attrib),depth+1))
                if node.text and node.text.strip():out.append(node.text.strip())
                for child in node:
                    if isinstance(child.tag,str):out.append(xml(child,depth+1))
                    if child.tail and child.tail.strip():out.append(child.tail.strip())
                return '\n\n'.join(out)
            body=xml(tree)
        return ParseResult(body,title=path.stem)

class CodeParser(BaseParser):
    extensions=('.css','.js','.ts','.py','.sql','.log','.ini','.cfg','.toml','.rst')
    def parse(self,path):
        text=read_text(path)
        fence='`'*max(3,max((len(x) for x in __import__('re').findall(r'`+',text)),default=0)+1)
        return ParseResult(f'{fence}{path.suffix.lstrip(".")}\n{text}\n{fence}',title=path.stem)
