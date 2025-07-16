from contextlib import suppress
from importlib.metadata import PackageNotFoundError, version
import logging

with suppress(PackageNotFoundError):
    __version__ = version("resonant-cli-oauth-client")

from .client import ResonantCliOAuthClient

logging.getLogger(__name__).addHandler(logging.NullHandler())

__all__ = ["ResonantCliOAuthClient"]
