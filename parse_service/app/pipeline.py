from __future__ import annotations
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
import yaml
from .registry import discover
from .detection import choose, UnsupportedFormat
PARSER_VERSION = "2.0"

ROOT = Path(__file__).resolve().parent.parent


def clean_name(name: str) -> str:
    return re.sub(r"[^\w\-.]+", "_", name, flags=re.UNICODE).strip("._") or "file"


def parse_one(source: Path, raw: Path, dest: Path, registry: dict, force: bool = False) -> str:
    rel = source.relative_to(raw)
    target = dest / rel.parent / (clean_name(source.name) + ".md")
    # If two formats share a basename in the same folder, suffix disambiguates.
    # Standard layout stores each format in its own directory.
    if source.stat().st_size > 128*1024*1024:
        raise ValueError("Файл превышает лимит 128 MiB")
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    sidecar = source.with_name(source.name + ".meta.json")
    extra = json.loads(sidecar.read_text(encoding="utf-8")) if sidecar.exists() else {}
    if not isinstance(extra,dict):
        raise ValueError("Sidecar должен быть JSON-объектом")
    if extra.get('include_in_rag') is False:
        target.unlink(missing_ok=True)
        return 'excluded'
    detected_format, parser = choose(source, registry)
    meta_digest=hashlib.sha256(sidecar.read_bytes() if sidecar.exists() else b'').hexdigest()
    if target.exists() and not force:
        old = target.read_text(encoding="utf-8")
        if (re.search(r"(?m)^sha256:\s*['\"]?" + digest, old)
            and "parser_version: '2.0'" in old
            and re.search(r"(?m)^metadata_sha256:\s*['\"]?"+meta_digest,old)):
            return "unchanged"
    parsed = parser.parse(source)
    if not parsed.markdown.strip():
        raise ValueError("Получен пустой текст")
    metadata = {
        "source": rel.as_posix(),
        "source_format": detected_format.lstrip("."),
        "original_extension": source.suffix.lower(),
        "parser": type(parser).__name__,
        "parser_version": PARSER_VERSION,
        "warnings": parsed.warnings,
        "title": parsed.title or source.stem,
        "category": "uncategorized",
        "vendor": "",
        "date_parsed": datetime.now(timezone.utc).date().isoformat(),
        "chunk_strategy": "hierarchical",
        "sha256": digest,
        "metadata_sha256": meta_digest,
    }
    if parsed.pages is not None:
        metadata["pages"] = parsed.pages
    if sidecar.exists():
        allowed = {"title", "category", "vendor", "source_url", "published_at", "language", "description",
                   "fetch_url","fetched_at","document_id","source_kind","last_modified","etag",
                   "archive_member","parent_sha256","source_file"}
        metadata.update({key: value for key, value in extra.items() if key in allowed})
    if extra.get('catalog_kind'):
        # appTitle is the title of an application; Title is only its subsection.
        metadata['title']=parsed.title
    yaml_text = yaml.safe_dump(metadata, allow_unicode=True, sort_keys=False, width=120).strip()
    body = parsed.markdown.strip()
    if not body.startswith("# "):
        body = "# " + str(metadata["title"]) + "\n\n" + body
    result = f"---\n{yaml_text}\n---\n\n{body}\n"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(result, encoding="utf-8")
    legacy=dest/rel.parent/(clean_name(source.stem)+'.md')
    if legacy!=target and legacy.is_file():
        try:
            header=yaml.safe_load(legacy.read_text(encoding='utf-8').split('---',2)[1])
            if header.get('source')==rel.as_posix():legacy.unlink()
        except (ValueError,IndexError,AttributeError,yaml.YAMLError):pass
    return "written"


def run(raw: Path, dest: Path, force: bool = False, verbose: bool = True) -> tuple[int, int]:
    if not raw.is_dir():raise ValueError(f'Папка raw не существует: {raw}')
    if dest==raw or raw in dest.parents:raise ValueError('parsed нельзя размещать внутри raw')
    registry=discover()
    counts=dict.fromkeys(['written','unchanged','excluded','unsupported','error'],0)
    records=[];ignored=0;total=0
    for source in sorted(raw.rglob('*')):
        if not source.is_file():continue
        total+=1
        if any(p.startswith('.') for p in source.relative_to(raw).parts) or source.name.endswith('.meta.json'):
            ignored+=1;continue
        record={'source':source.relative_to(raw).as_posix(),'bytes':source.stat().st_size}
        try:
            status=parse_one(source,raw,dest,registry,force)
            target=dest/source.relative_to(raw).parent/(clean_name(source.name)+'.md')
            if status in ('written','unchanged'):
                header=yaml.safe_load(target.read_text(encoding='utf-8').split('---',2)[1])
                record.update(output=str(target),parser=header.get('parser'),detected_format=header['source_format'],warnings=header.get('warnings',[]))
            elif status=='excluded':record['reason']='include_in_rag=false в .meta.json'
        except UnsupportedFormat as e:
            status='unsupported';record['reason']=str(e)
        except Exception as e:
            status='error';record['reason']=f'{type(e).__name__}: {e}'
        record['status']=status;records.append(record);counts[status]+=1
        if verbose:print(f"[{status}] {record['source']}"+(' — '+record['reason'] if record.get('reason') else ''))
    report=dest.parent/'registry';report.mkdir(parents=True,exist_ok=True)
    (report/'parsing_report.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in records),encoding='utf-8')
    summary={'raw_total_files':total,'ignored_metadata_and_hidden':ignored,'input_documents':len(records),**counts}
    (report/'parsing_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Итог:',', '.join(f'{k}={v}' for k,v in summary.items()))
    return counts['written'],counts['error']
