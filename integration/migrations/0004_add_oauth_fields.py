# Generated migration to add OAuth2 support for pasons.live

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('integration', '0003_add_api_push_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='outlet',
            name='pasons_client_id',
            field=models.CharField(
                blank=True,
                null=True,
                max_length=255,
                help_text='OAuth2 Client ID for pasons.live API'
            ),
        ),
        migrations.AddField(
            model_name='outlet',
            name='pasons_client_secret',
            field=models.CharField(
                blank=True,
                null=True,
                max_length=500,
                help_text='OAuth2 Client Secret for pasons.live API (encrypted)'
            ),
        ),
        migrations.AddField(
            model_name='outlet',
            name='pasons_access_token',
            field=models.TextField(
                blank=True,
                null=True,
                help_text='Current OAuth2 access token (JWT)'
            ),
        ),
        migrations.AddField(
            model_name='outlet',
            name='pasons_refresh_token',
            field=models.TextField(
                blank=True,
                null=True,
                help_text='OAuth2 refresh token for token renewal'
            ),
        ),
        migrations.AddField(
            model_name='outlet',
            name='pasons_token_expires_at',
            field=models.DateTimeField(
                blank=True,
                null=True,
                help_text='Timestamp when access token expires'
            ),
        ),
    ]
