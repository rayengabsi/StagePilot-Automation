from __future__ import annotations

from alembic.config import Config


def test_alembic_config_loads_script_location() -> None:
    """Alembic configuration should point at the project migration directory."""
    config = Config("alembic.ini")

    assert config.get_main_option("script_location") == "alembic"
