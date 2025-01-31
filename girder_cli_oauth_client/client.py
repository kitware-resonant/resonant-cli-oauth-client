from dataclasses import dataclass, field
import datetime
import json
import os
from pathlib import Path
import shutil
import time
from typing import Dict, Literal, Optional
from urllib.parse import urlencode, urlparse
import webbrowser

from authlib.common.security import generate_token
from authlib.integrations.requests_client import OAuth2Session
from dataclasses_json import dataclass_json
import requests
from xdg import BaseDirectory

AuthHeaders = Dict

@dataclass_json
@dataclass
class AccessToken:
    token_type: str
    access_token: str
    expires_in: int
    scope: str # TODO list?
    refresh_token: str


    # This is a non-standard field we add to make it easier to check for expiration. This is
    # to minimize the number of times we need to retrieve a new token.
    # The name originates from a field that was mistakenly added in oauthlib, but never
    # implemented for the device flow.
    # It also mirrors the field/behavior used by the JS client:
    # https://github.com/openid/AppAuth-JS/blob/b3936d8b83501713130a21c4f870f1b9e66ebfa8/src/token_response.ts#L83
    issued_at: datetime.datetime = field(default_factory=datetime.datetime.now)

    @property
    def is_expired(self) -> bool:
        return datetime.datetime.now(datetime.UTC) > self.issued_at + datetime.timedelta(seconds=self.expires_in)

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
    error: Literal['expired_token', 'access_denied']


class GirderCliOAuthClient:
    _token: AccessToken | None
    _authorization_response: AuthorizationResponse | None

    def __init__(self, oauth_url: str, client_id: str, scopes: Optional[list[str]] = None) -> None:
        self.oauth_url = oauth_url.rstrip('/')
        self.client_id = client_id
        self._scopes = [] if not scopes else scopes
        self._token = None
        self._session = requests.Session()
        self._authorization_response = None

    @property
    def _data_path(self) -> Path:
        hostname = urlparse(self.oauth_url).hostname
        assert hostname
        namespace = Path('girder_cli_oauth_client') / Path(hostname) / Path(self.client_id)
        return Path(BaseDirectory.save_data_path(namespace))

    @property
    def _token_path(self) -> Path:
        return self._data_path / 'token.json'

    @property
    def scope(self) -> str:
        return ' '.join(self._scopes)

    def _load(self) -> None:
        if self._token_path.exists():
            with open(self._token_path, 'r') as infile:
                self._token = AccessToken.from_json(infile.read(), infer_missing=True)

    def _save(self) -> None:
        if self._token:
            with open(self._token_path, 'w') as outfile:
                outfile.write(self._token.to_json(indent=4))
    @property
    def auth_headers(self) -> AuthHeaders | None:
        if self._token:
            auth_value = (
                f'{self._token.token_type} {self._token.access_token}'
            )
            return {'Authorization': auth_value}
        else:
            return None

    def initialize_login_flow(self) -> AuthorizationResponse:
        response = self._session.post(
            f'{self.oauth_url}/device-authorization/',
            data={
                'client_id': self.client_id,
                'scope': self.scope,
            },
        )

        response.raise_for_status()

        return AuthorizationResponse.from_json(response.text, infer_missing=True)

    def refresh_token(self) -> None:
        if not self._token:
            raise ValueError('no token to refresh')

        r = self._session.post(f'{self.oauth_url}/token/',
                               headers={
                                   'Content-Type': 'application/x-www-form-urlencoded',
                               },
                               data={
                                   'client_id': self.client_id,
                                   'grant_type': 'refresh_token',
                                   'refresh_token': self._token.refresh_token,
                               })
        if r.ok:
            self._token = AccessToken.from_json(r.text, infer_missing=True)
            self._save()
        else:
            raise Exception(f'failed to refresh token: {r.status_code}')

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
                except Exception as e:
                    self.logout()

            if set(self._token.scope.split()) < set(self._scopes):
                # One or more requested scopes aren't provided in the existing token. This is really
                # common when developing and modifying the scopes parameter. This invalidates
                # the cached token, so log the user out so a new login flow begins.
                # Use an inequality comparison, as sometimes the scopes returned are different from
                # the scopes requested; usually though, this is the server returning more scopes.
                self.logout()

        return self.auth_headers

    def wait_for_completion(self, authorization_response: AuthorizationResponse, max_wait: int = 300) -> AuthHeaders | TokenResponseError:   # type: ignore
        slow_down_factor = 0

        start_time = time.time()
        while time.time() - start_time < max_wait:
            response = self._session.post(
                f'{self.oauth_url}/token/',
                headers={
                    'Content-Type': 'application/x-www-form-urlencoded',
                },
                data={
                    'client_id': self.client_id,
                    'device_code': authorization_response.device_code,
                    'grant_type': 'urn:ietf:params:oauth:grant-type:device_code',
                    'scope': self.scope,
                },
            )

            if response.status_code == 200:
                self._token = AccessToken.from_json(response.text, infer_missing=True)
                self._save()
                assert self.auth_headers
                return self.auth_headers
            elif response.status_code == 400:
                error = response.json()['error']
                if error == 'authorization_pending':
                    time.sleep(authorization_response.interval + (slow_down_factor * 5))
                elif error == 'slow_down':
                    slow_down_factor += 1
                elif error == 'expired_token':
                    return TokenResponseError(error='expired_token')
                elif error == 'access_denied':
                    return TokenResponseError(error='access_denied')
                else:
                    raise Exception(f'error: {error}')
            else:
                raise Exception(f'error: {response.status_code}')

            time.sleep(authorization_response.interval + (slow_down_factor * 5))

        raise Exception("timed out waiting for token response")

    def logout(self) -> bool:
        if self._token:
            r = self._session.post(f'{self.oauth_url}/revoke_token/',
                                   data={
                                       'token': self._token.access_token,
                                       'client_id': self.client_id,
                                   })
            if not r.ok:
                return False

        if self._token_path.exists():
            self._token_path.unlink()

        return True
