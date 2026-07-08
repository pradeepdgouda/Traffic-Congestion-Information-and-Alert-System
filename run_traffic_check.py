from django.core.management.base import BaseCommand
from traffic.tasks import check_all_saved_routes


class Command(BaseCommand):
    help = 'Run a single pass of traffic checks for saved routes.'

    def handle(self, *args, **options):
        results = check_all_saved_routes()
        self.stdout.write(self.style.SUCCESS(f"Checked: {results.get('checked')}, Alerts sent: {results.get('alerts_sent')}"))
