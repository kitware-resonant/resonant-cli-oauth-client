# resonant-cli-oauth-client

A Python library for performing OAuth login to a Resonant server.

## Description
This provides support for authenticating with Resonant servers
using the OAuth2.0 Device Code Grant.

## Usage
* Install the library:
  ```bash
  pip install resonant-cli-oauth-client
  ```

* Instantiate an `OauthClient` with your application-specific configuration:
  ```py
  from resonant_cli_oauth_client import ResonantCliOAuthClient

  oauth_client = ResonantCliOAuthClient(
      'http://127.0.0.1:8000/oauth/',
      'jUQhgOTQYiG6hmNSvaodOGJeriAqA1anqo8WFjCw',
      ['identity'],
  )
  ```

* Call `login` when it's time to start a login flow:
  ```py
  oauth_client.initialize_login_flow()  # retrieve the url and code for the user to enter
  oauth_client.wait_for_completion()  # wait for the user to complete the login flow
  ```

* At the start of *every* application start, unconditionally call `maybe_restore_login`, to attempt to
  restore a login state; this will no-op if no login is present.
  ```py
  oauth_client.maybe_restore_login()
  ```

* Include these headers with every API request:
  ```py
  requests.get('http://localhost:8000/api/users/me', headers=oauth_client.auth_headers)
  ```

* Call `logout` to clear any active login:
  ```py
  oauth_client.logout()
  ```

## Example app
This repository comes bundled with an [example application](example/cli.py). Run it with:
```bash
git clone https://github.com/kitware-resonant/resonant-cli-oauth-client.git
pip install -e '.[example]'
cd example
./manage.py migrate
./manage.py createsuperuser
./manage.py runserver
# log in to your account at http://127.0.0.1:8000/admin
# in another tab
python cli.py login
python cli.py me
```
