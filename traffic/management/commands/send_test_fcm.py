from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.conf import settings
from traffic.models import UserProfile, UserFcmDevice, SavedRoute
from traffic.notification_service import send_notification_to_token, save_fcm_token, send_congestion_alert_for_route
from django.utils import timezone
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Save an FCM token for a user and send a test notification'

    def add_arguments(self, parser):
        parser.add_argument('--username', '-u', required=True, help='Username to associate the token with')
        parser.add_argument('--token', '-t', required=True, help='FCM registration token')

    def handle(self, *args, **options):
        username = options['username']
        token = options['token']

        User = get_user_model()
        user = User.objects.filter(username=username).first()
        if not user:
            # create a lightweight user for testing
            user = User.objects.create_user(username=username, password='changeme')
            self.stdout.write(self.style.NOTICE(f'Created test user {username}'))

        profile, _ = UserProfile.objects.get_or_create(user=user)

        # save/update token in UserFcmDevice and profile
        try:
            UserFcmDevice.objects.update_or_create(user_profile=profile, defaults={'fcm_token': token})
        except Exception:
            # fallback to simple create if update_or_create fails
            try:
                UserFcmDevice.objects.create(user_profile=profile, fcm_token=token)
            except Exception as e:
                self.stderr.write(f'Failed to store token in UserFcmDevice: {e}')
                return

        profile.fcm_token = token
        profile.save(update_fields=['fcm_token'])

        self.stdout.write(self.style.SUCCESS(f'Token stored for {username}'))

        # Send test notification
        title = 'Test Traffic Alert'
        body = 'This is a test notification from the backend.'
        ok = send_notification_to_token(token, title, body, data={'test':'1'})
        if ok:
            self.stdout.write(self.style.SUCCESS('Notification send succeeded'))
        else:
            self.stderr.write('Notification send failed - see logs for details')

        # Create a SavedRoute scheduled to alert now (simulate scheduled behavior)
        try:
            now = timezone.now()
            route = SavedRoute.objects.create(
                user=user,
                username=username,
                origin='Test Origin',
                destination='Test Destination',
                alert_enabled=True,
                alert_time=(now + timedelta(seconds=5)).time(),
            )
            self.stdout.write(self.style.SUCCESS(f'Created test SavedRoute {route.route_id} with alert_time {route.alert_time}'))

            # Trigger a scheduled-style send immediately by calling the notifier
            sent = send_congestion_alert_for_route(route, severity='Moderate')
            if sent:
                self.stdout.write(self.style.SUCCESS('Scheduled-style notification sent to saved token'))
            else:
                self.stderr.write('Scheduled-style notification failed - check logs')
        except Exception as e:
            self.stderr.write(f'Failed to create or trigger SavedRoute: {e}')