from django.http import JsonResponse
from oauth2_provider.decorators import protected_resource


@protected_resource()
def me(request):
    user = request.user
    return JsonResponse(
        {
            "email": user.email,
        }
    )
