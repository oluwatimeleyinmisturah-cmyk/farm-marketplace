from django.core.management.base import BaseCommand
from django.contrib.auth.models import User

class Command(BaseCommand):
    def handle(self, *args, **kwargs):
        if not User.objects.filter(username='OlaWale').exists():
            User.objects.create_superuser(
                'OlaWale',
                'thesanniolawales@gmail.com',
                'JeliliSanni'
            )
            self.stdout.write("Admin created")
        else:
            self.stdout.write("Admin already exists")
