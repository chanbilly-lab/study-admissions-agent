from pathlib import Path
from alembic import command
from alembic.config import Config


def migrate(engine):
    """Run the same frozen Alembic migration in offline tests and deployment."""
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
