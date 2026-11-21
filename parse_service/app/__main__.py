import argparse
from .pipeline import ROOT, run
from .registry import discover


def main():
    cmd = argparse.ArgumentParser(description="Конвертация локальных документов в Markdown с YAML front matter")
    cmd.add_argument("--raw", default=str(ROOT / "raw"), help="Папка исходников")
    cmd.add_argument("--out", default=str(ROOT / "parsed"), help="Папка результата")
    cmd.add_argument("--force", action="store_true", help="Пересоздать даже неизменившиеся файлы")
    cmd.add_argument("--list-formats", action="store_true", help="Показать поддерживаемые расширения")
    args = cmd.parse_args()
    if args.list_formats:
        print("Форматы:", ", ".join(sorted(discover())))
        return
    from pathlib import Path
    written, errors = run(Path(args.raw).resolve(), Path(args.out).resolve(), force=args.force)
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
