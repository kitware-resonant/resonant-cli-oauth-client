import click
import requests

from girder_cli_oauth_client import GirderCliOAuthClient


@click.group()
@click.pass_context
def cli(ctx):
    ctx.obj['client'] = GirderCliOAuthClient(
        'http://127.0.0.1:8000/oauth',
        'jUQhgOTQYiG6hmNSvaodOGJeriAqA1anqo8WFjCw',
        ['identity'],
    )

    ctx.obj['auth_headers'] = ctx.obj['client'].maybe_restore_login()


@cli.command()
@click.pass_context
def login(ctx):
    if not ctx.obj['auth_headers']:
        authorization_response = ctx.obj['client'].initialize_login_flow()
        click.echo(f'visit the following url in a browser: {authorization_response.verification_uri}')
        click.echo(f'user code: {authorization_response.user_code}')

        ctx.obj['client'].wait_for_completion(authorization_response)

        click.echo('Success, try running "me" to see your user info.')
    else:
        click.echo('Already logged in, try running "me" to see your user info.')


@cli.command()
@click.pass_context
def logout(ctx):
    if ctx.obj['auth_headers']:
        ctx.obj['client'].logout()
        click.echo('Successfully logged out.')
    else:
        click.echo('Not currently logged in.')


@cli.command()
@click.pass_context
def me(ctx):
    if not ctx.obj['auth_headers']:
        click.echo('Not logged in, try the "login" command.')
    else:
        r = requests.get('http://127.0.0.1:8000/me/', headers=ctx.obj['auth_headers'])
        r.raise_for_status()
        click.echo(f'hello {r.json()["email"]}!')


if __name__ == '__main__':
    cli(obj={})
