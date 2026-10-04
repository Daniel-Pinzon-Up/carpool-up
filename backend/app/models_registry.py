import importlib
import pkgutil

import app.modules


def import_all_models() -> None:
    """Importa cada app/modules/*/models.py para que Alembic vea todas las tablas."""
    for module in pkgutil.iter_modules(app.modules.__path__):
        try:
            importlib.import_module(f"app.modules.{module.name}.models")
        except ModuleNotFoundError as exc:
            if exc.name != f"app.modules.{module.name}.models":
                raise
