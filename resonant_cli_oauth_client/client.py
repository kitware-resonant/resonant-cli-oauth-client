from dataclasses import dataclass, field
import datetime
from functools import cache
import json
import logging
from pathlib import Path
import time
from typing import Literal, Optional
from urllib.parse import urlparse

from dataclasses_json import dataclass_json
import requests
from xdg import BaseDirectory

AuthHeaders = dict

logger = logging.getLogger(__name__)


@dataclass_json
@dataclass(frozen=True)
class OpenIDConfig:
    device_authorization_endpoint: str
    token_endpoint: str
    userinfo_endpoint: str
    revocation_endpoint: str


@dataclass_json
@dataclass
class AccessToken:
    token_type: str
    access_token: str
    expires_in: int
    scope: str  # TODO: list?
    refresh_token: str

    # This is a non-standard field we add to make it easier to check for expiration. This is
    # to minimize the number of times we need to retrieve a new token.
    # The name originates from a field that was mistakenly added in oauthlib, but never
    # implemented for the device flow.
    # It also mirrors the field/behavior used by the JS client:
    # https://github.com/openid/AppAuth-JS/blob/b3936d8b83501713130a21c4f870f1b9e66ebfa8/src/token_response.ts#L83
    issued_at: datetime.datetime = field(
        default_factory=lambda: datetime.datetime.now(datetime.UTC)
    )

    @property
    def is_expired(self) -> bool:
        return datetime.datetime.now(datetime.UTC) > self.issued_at + datetime.timedelta(
            seconds=self.expires_in
        )


@dataclass_json
@dataclass
class AuthorizationResponse:
    device_code: str
    user_code: str
    verification_uri: str
    verification_uri_complete: str | None
    expires_in: int
    interval: int


@dataclass
class TokenResponseError:
    error: Literal["expired_token", "access_denied"]


class ResonantCliOAuthClient:
    _token: AccessToken | None
    _authorization_response: AuthorizationResponse | None

    def __init__(self, oauth_url: str, client_id: str, scopes: list[str] | None = None) -> None:
        self.oauth_url = oauth_url.rstrip("/")
        self.client_id = client_id
        self._scopes = scopes if scopes else []
        self._token = None
        self._session = requests.Session()
        self._authorization_response = None

    @property
    def _data_path(self) -> Path:
        hostname = urlparse(self.oauth_url).hostname
        assert hostname  # noqa: S101
        namespace = Path("resonant_cli_oauth_client") / Path(hostname) / Path(self.client_id)
        return Path(BaseDirectory.save_data_path(namespace))

    @property
    def _token_path(self) -> Path:
        return self._data_path / "token.json"

    @property
    def scope(self) -> str:
        return " ".join(self._scopes)

    def _load(self) -> None:
        if self._token_path.exists():
            with self._token_path.open() as infile:
                self._token = AccessToken.from_json(infile.read(), infer_missing=True)

    def _save(self) -> None:
        if self._token:
            with self._token_path.open("w") as outfile:
                outfile.write(self._token.to_json(indent=4))

    @property
    def auth_headers(self) -> AuthHeaders | None:
        if self._token:
            auth_value = f"{self._token.token_type} {self._token.access_token}"
            return {"Authorization": auth_value}
        else:
            return None

    @cache
    def _get_openid_config(self) -> OpenIDConfig:
        response = self._session.get(f'{self.oauth_url}/.well-known/openid-configuration')
        response.raise_for_status()
        return OpenIDConfig.from_json(response.text)

    def _get_url(
        self, type_: Literal['device_authorization', 'token', 'userinfo', 'revocation']
    ) -> str:
        openid_config = self._get_openid_config()

        if type_ == 'device_authorization':
            return openid_config.device_authorization_endpoint
        elif type_ == 'token':
            return openid_config.token_endpoint
        elif type_ == 'userinfo':
            return openid_config.userinfo_endpoint
        elif type_ == 'revocation':
            return openid_config.revocation_endpoint
        else:
            raise ValueError(f'invalid type: {type_}')

    def initialize_login_flow(self) -> AuthorizationResponse:
        response = self._session.post(
            self._get_url('device_authorization'),
            data={
                "client_id": self.client_id,
                "scope": self.scope,
            },
        )
        logger.debug(f'response: {response.text}')

        response.raise_for_status()

        return AuthorizationResponse.from_json(response.text, infer_missing=True)

    def refresh_token(self) -> None:
        if not self._token:
            raise ValueError("no token to refresh")

        r = self._session.post(
            self._get_url('token'),
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={
                "client_id": self.client_id,
                "grant_type": "refresh_token",
                "refresh_token": self._token.refresh_token,
            },
        )

        logger.debug(f'response: {r.text}')

        if r.ok:
            self._token = AccessToken.from_json(r.text, infer_missing=True)
            self._save()
        else:
            raise Exception(f"failed to refresh token: {r.status_code}")

    def maybe_restore_login(self) -> AuthHeaders | None:
        """
        Attempt to restore an existing login if it exists and is not expired.

        This is a best effort, since the token can be revoked out of band at any moment
        and the client would have no way of knowing.
        """
        self._load()

        if self._token:
            if self._token.is_expired:
                try:
                    self.refresh_token()
                except Exception:  # noqa: BLE001
                    self.logout()

            if set(self._token.scope.split()) < set(self._scopes):
                # One or more requested scopes aren't provided in the existing token. This is really
                # common when developing and modifying the scopes parameter. This invalidates
                # the cached token, so log the user out so a new login flow begins.
                # Use an inequality comparison, as sometimes the scopes returned are different from
                # the scopes requested; usually though, this is the server returning more scopes.
                self.logout()

        return self.auth_headers

    def wait_for_completion(self, authorization_response: AuthorizationResponse, max_wait: int = 300) -> AuthHeaders:
        slow_down_factor = 0

        start_time = time.time()
        while time.time() - start_time < max_wait:
            response = self._session.post(
                self._get_url('token'),
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                data={
                    "client_id": self.client_id,
                    "device_code": authorization_response.device_code,
                    "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                    "scope": self.scope,
                },
            )

            logger.debug(f'response: {response.text}')

            if response.status_code == 200:
                self._token = AccessToken.from_json(response.text, infer_missing=True)
                self._save()
                assert self.auth_headers  # noqa: S101
                return self.auth_headers
            elif response.status_code == 400:
                error = response.json()["error"]
                if error == "authorization_pending":
                    time.sleep(authorization_response.interval + (slow_down_factor * 5))
                elif error == "slow_down":
                    slow_down_factor += 1
                elif error == "expired_token":
                    return TokenResponseError(error="expired_token")
                elif error == "access_denied":
                    return TokenResponseError(error="access_denied")
                else:
                    raise Exception(f"error: {error}")
            else:
                raise Exception(f"error: {response.status_code}")

            time.sleep(authorization_response.interval + (slow_down_factor * 5))

        raise Exception('timed out waiting for device code to be submitted')

    def logout(self) -> bool:
        if self._token:
            r = self._session.post(
                self._get_url('revocation'),
                data={
                    "token": self._token.access_token,
                    "client_id": self.client_id,
                },
            )
            logger.debug(f'response: {r.text}')
            if not r.ok:
                return False

        if self._token_path.exists():
            self._token_path.unlink()

        return True
