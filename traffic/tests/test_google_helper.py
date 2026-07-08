from django.test import TestCase
from unittest.mock import patch
from traffic.utils.google_directions import get_live_traffic


class GoogleHelperTests(TestCase):
    @patch('traffic.utils.google_directions.requests.get')
    def test_get_live_traffic_handles_error(self, mock_get):
        mock_get.side_effect = Exception('network')
        res = get_live_traffic('A', 'B')
        self.assertIn('error', res)
