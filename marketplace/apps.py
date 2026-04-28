from django.apps import AppConfig

class MarketplaceConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'marketplace'

    def ready(self):
        import marketplace.signals

        from django.contrib.auth.models import User

        if not User.objects.filter(username='OlaWale').exists():
            User.objects.create_superuser(
                'OlaWale',
                'thesanniolawales@gmail.com',
                'JeliliSanni101'
            )
