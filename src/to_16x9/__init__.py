"""把照片轉成 16:9 比例。"""
from ._version import __version__
from .cli import convert, main

__all__ = ["__version__", "convert", "main"]
