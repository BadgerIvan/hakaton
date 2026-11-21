"""Discover plugins automatically. To add a format, drop a module in app/parsers/."""
import importlib
import inspect
import pkgutil
from pathlib import Path
from .parsers import __path__ as plugin_paths
from .parsers.base import BaseParser


def discover() -> dict[str, BaseParser]:
    result: dict[str, BaseParser] = {}
    for info in pkgutil.iter_modules(plugin_paths):
        if info.name == "base" or info.name.startswith("_"):
            continue
        module = importlib.import_module(f"app.parsers.{info.name}")
        for _, cls in inspect.getmembers(module, inspect.isclass):
            if not issubclass(cls, BaseParser) or cls is BaseParser or cls.__module__ != module.__name__ or inspect.isabstract(cls):
                continue
            instance = cls()
            for ext in instance.extensions:
                key = ext.lower()
                if key in result:
                    raise RuntimeError(f"Дублирующийся парсер для {key}")
                result[key] = instance
    return result
