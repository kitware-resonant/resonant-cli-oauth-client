# Generated by Django 5.1.5 on 2025-01-28 17:31

from django.db import migrations


def create_device_code_oauth_application(apps, schema_editor):
    Application = apps.get_model('oauth2_provider', 'Application')
    Application.objects.create(
        client_id="jUQhgOTQYiG6hmNSvaodOGJeriAqA1anqo8WFjCw",
        client_secret="test",
        name="example",
        redirect_uris="http://127.0.0.1:8000/",
        client_type="public",
        authorization_grant_type="urn:ietf:params:oauth:grant-type:device_code",
    )


class Migration(migrations.Migration):
    dependencies = [
        ('oauth2_provider', '0013_alter_application_authorization_grant_type_device'),
    ]

    operations = [
        migrations.RunPython(create_device_code_oauth_application),
    ]
