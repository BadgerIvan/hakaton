from __future__ import annotations
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
import yaml
from .registry import discover

ROOT = Path(__file__).resolve().parent.parent


def clean_name(name: str) -> str:
    return re.sub(r"[^\w\-.]+", "_", name, flags=re.UNICODE).strip("._") or "file"


def parse_one(source: Path, raw: Path, dest: Path, registry: dict, force: bool = False) -> str:
    parser = registry.get(source.suffix.lower())
    if not parser:
        return "unsupported"
    rel = source.relative_to(raw)
    target = dest / rel.parent / (clean_name(source.stem) + ".md")
    # If two formats share a basename in the same folder, suffix disambiguates.
    # Standard layout stores each format in its own directory.
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    if target.exists() and not force:
        old = target.read_text(encoding="utf-8")
        if re.search(r"(?m)^sha256:\s*['\"]?" + digest, old):
            return "unchanged"
    parsed = parser.parse(source)
    if not parsed.markdown.strip():
        raise ValueError("Получен пустой текст")
    metadata = {
        "source": rel.as_posix(),
        "source_format": source.suffix.lower().lstrip("."),
        "title": parsed.title or source.stem,
        "category": "uncategorized",
        "vendor": "",
        "date_parsed": datetime.now(timezone.utc).date().isoformat(),
        "chunk_strategy": "hierarchical",
        "sha256": digest,
    }
    if parsed.pages is not None:
        metadata["pages"] = parsed.pages
    sidecar = source.with_name(source.name + ".meta.json")
    if sidecar.exists():
        extra = json.loads(sidecar.read_text(encoding="utf-8"))
        allowed = {"title", "category", "vendor", "source_url", "published_at", "language", "description"}
        if not isinstance(extra, dict):
            raise ValueError("Sidecar должен быть JSON-объектом")
        metadata.update({key: value for key, value in extra.items() if key in allowed})
    yaml_text = yaml.safe_dump(metadata, allow_unicode=True, sort_keys=False, width=120).strip()
    body = parsed.markdown.strip()
    if not body.startswith("# "):
        body = "# " + str(metadata["title"]) + "\n\n" + body
    result = f"---\n{yaml_text}\n---\n\n{body}\n"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(result, encoding="utf-8")
    return "written"


def run(raw: Path, dest: Path, force: bool = False, verbose: bool = True) -> tuple[int, int]:
    registry = discover()
    counts = {"written": 0, "unchanged": 0, "unsupported": 0, "error": 0}
    for source in sorted(raw.rglob("*")):
        if not source.is_file() or source.name.startswith(".") or source.name.endswith(".meta.json") or source.name == ".gitkeep":
            continue
        if source.suffix.lower() not in registry:
            counts["unsupported"] += 1
            continue
        try:
            status = parse_one(source, raw, dest, registry, force)
            counts[status] += 1
            if verbose:
                print(f"[{status}] {source.relative_to(raw)}")
        except Exception as ex:
            counts["error"] += 1
            print(f"[ERROR] {source.relative_to(raw)}: {ex}")
    print("Итог:", ", ".join(f"{key}={value}" for key, value in counts.items()))
    return counts["written"], counts["error"]
