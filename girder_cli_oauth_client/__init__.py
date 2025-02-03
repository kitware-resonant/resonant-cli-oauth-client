from contextlib import suppress
from importlib.metadata import PackageNotFoundError, version

with suppress(PackageNotFoundError):
    __version__ = version("resonant-cli-oauth-client")

from .client import ResonantCliOAuthClient

__all__ = ["ResonantCliOAuthClient"]
