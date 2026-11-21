"""Copy legacy auth data transactionally. SQLite is read-only, PostgreSQL is the target."""
import argparse
import sqlite3
from pathlib import Path
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from .config import Settings
from .database import Base, build_engine
from .migrate import upgrade

TABLES = ('auth_users', 'auth_sessions', 'auth_rate_limits')


def migrate(source_path, target_url, *, dry_run=False):
    path = Path(source_path).resolve(strict=True)
    engine = build_engine(target_url)
    if not dry_run:
        upgrade(target_url)
    counts = {}
    source = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)
    source.row_factory = sqlite3.Row
    try:
        with source, engine.begin() as target:
            # One read snapshot and one target transaction for all three tables.
            source.execute('BEGIN')
            for name in TABLES:
                table = Base.metadata.tables[name]
                primary_key = next(iter(table.primary_key.columns))
                count = 0
                for row in source.execute(f'SELECT * FROM {name}'):
                    values = dict(row)
                    if not dry_run:
                        existing = target.execute(select(table).where(primary_key == values[primary_key.name])).mappings().first()
                        if existing is not None:
                            if dict(existing) != values:
                                raise ValueError(f'Conflicting data in {name}; PostgreSQL transaction rolled back')
                        else:
                            target.execute(table.insert().values(**values))
                    count += 1
                counts[name] = count
    except IntegrityError:
        raise ValueError('Data conflict (email or foreign key); PostgreSQL transaction rolled back') from None
    finally:
        source.close()
        engine.dispose()
    return counts


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, help='Path to legacy auth.db')
    parser.add_argument('--dry-run', action='store_true', help='Validate/read the source without changing PostgreSQL')
    args = parser.parse_args()
    print(migrate(args.source, Settings().database_url, dry_run=args.dry_run))
