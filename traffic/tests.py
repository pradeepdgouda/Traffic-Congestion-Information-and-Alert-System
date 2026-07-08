from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model
from .models import UserFcmDevice, UserProfile


class SaveFcmTokenTest(TestCase):
	def setUp(self):
		self.client = APIClient()
		User = get_user_model()
		self.user = User.objects.create_user(username='alice', password='pass')

	def test_save_fcm_token_creates_device(self):
		url = reverse('save_fcm_token')
		payload = {'username': 'alice', 'token': 'fake_token_12345'}
		resp = self.client.post(url, payload, format='json')
		self.assertEqual(resp.status_code, 200)
		self.assertEqual(resp.json(), {'status': 'Token saved'})
		profile = UserProfile.objects.get(user__username='alice')
		# ensure profile token updated
		self.assertEqual(profile.fcm_token, 'fake_token_12345')
		# ensure UserFcmDevice exists
		dev = UserFcmDevice.objects.filter(user_profile=profile).first()
		self.assertIsNotNone(dev)
		self.assertEqual(dev.fcm_token, 'fake_token_12345')

	def test_save_fcm_token_missing_params(self):
		url = reverse('save_fcm_token')
		resp = self.client.post(url, {'username': 'alice'}, format='json')
		self.assertEqual(resp.status_code, 400)
