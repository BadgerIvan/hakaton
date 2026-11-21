from pathlib import Path
from alembic import command
from alembic.config import Config
from .config import Settings


def upgrade(database_url=None):
    config = Config(str(Path(__file__).resolve().parents[1] / 'alembic.ini'))
    config.attributes['database_url'] = database_url or Settings().database_url
    command.upgrade(config, 'head')


if __name__ == '__main__':
    upgrade()
