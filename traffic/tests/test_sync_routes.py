from django.test import TestCase
from django.urls import reverse
from django.contrib.auth.models import User
import json


class SyncRoutesTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='alice', password='pass')

    def test_sync_create_route(self):
        url = reverse('sync_routes')
        payload = {
            'username': 'alice',
            'routes': [
                {
                    'origin': 'A',
                    'destination': 'B',
                    'distance_km': 12.3,
                    'duration_text': '15 mins',
                    'polyline': 'abc',
                    'leaving_time': '12:30',
                    'alert_time': '12:15',
                    'selected_routes': [],
                    'alternatives': []
                }
            ]
        }
        resp = self.client.post(url, data=json.dumps(payload), content_type='application/json')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['created'], 1)
