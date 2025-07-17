from allauth.idp.oidc.internal.oauthlib.server import get_server
from allauth.idp.oidc.internal.oauthlib.utils import extract_params
from allauth.idp.oidc.internal.scope import is_scope_granted
from django.http import JsonResponse


def me(request):
    # this is a contrived way to get the user info from the access token and verify
    # the scopes are correct. typically the ninja/drf integrations would be used instead.
    server = get_server()
    orequest = extract_params(request)
    valid, ctx = server.verify_request(*orequest, scopes=[])

    if not valid:
        return JsonResponse({"detail": "Forbidden"}, status=403)

    if not is_scope_granted("openid", ctx.access_token, request.method):
        return JsonResponse({"detail": "Forbidden"}, status=403)

    if access_token := ctx.access_token:
        request.user = access_token.user

    return JsonResponse(
        {
            "email": request.user.email,
        }
    )
