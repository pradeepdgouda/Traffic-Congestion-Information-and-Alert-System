from django.test import TestCase
from unittest.mock import patch
from traffic.notification_service import send_route_notification


class NotificationTests(TestCase):
    @patch('traffic.notification_service.messaging.send')
    @patch('traffic.notification_service._init_firebase')
    def test_send_route_notification_calls_firebase(self, mock_init, mock_send):
        mock_send.return_value = 'message-id-123'
        res = send_route_notification('fake-token', 'title', 'body')
        self.assertEqual(res, 'message-id-123')
