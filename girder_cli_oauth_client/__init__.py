from contextlib import suppress
from importlib.metadata import PackageNotFoundError, version

with suppress(PackageNotFoundError):
    __version__ = version("girder-cli-oauth-client")

from .client import GirderCliOAuthClient

__all__ = ["GirderCliOAuthClient"]
