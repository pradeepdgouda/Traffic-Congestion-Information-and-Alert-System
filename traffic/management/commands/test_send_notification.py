from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from traffic.notification_service import send_congestion_alert

User = get_user_model()

class Command(BaseCommand):
    help = 'Send a test congestion notification to a user by username'

    def add_arguments(self, parser):
        parser.add_argument('username', type=str, help='Username to send notification to')

    def handle(self, *args, **options):
        username = options['username']
        user = User.objects.filter(username=username).first()
        if not user:
            self.stderr.write(self.style.ERROR(f'User not found: {username}'))
            return

        title = '🚦 Traffic Alert'
        body = '🚦 Traffic Alert: Heavy congestion detected on your saved route.'
        ok = send_congestion_alert(user, title, body)
        if ok:
            self.stdout.write(self.style.SUCCESS(f'Notification sent to {username}'))
        else:
            self.stderr.write(self.style.ERROR(f'Failed to send notification to {username}'))
