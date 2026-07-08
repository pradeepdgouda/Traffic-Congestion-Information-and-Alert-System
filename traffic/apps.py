from django.apps import AppConfig


class TrafficConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'traffic'
    def ready(self):
        # start the background traffic checker scheduler
        try:
            # When running the development server with the autoreloader, App.ready
            # can be called twice. Only start the scheduler in the reloader main
            # process to avoid duplicate schedulers. The autoreloader sets
            # RUN_MAIN to 'true' in the child process that should run code.
            import os
            if os.environ.get('RUN_MAIN') != 'true' and os.environ.get('DJANGO_RUN_MAIN') != 'true':
                # Not in the autoreloader child process; skip scheduler start.
                return

            from .traffic_checker import start_scheduler
            start_scheduler()
        except Exception:
            # avoid crashing startup if scheduler can't start
            import traceback
            print('Failed to start traffic checker scheduler')
            traceback.print_exc()
