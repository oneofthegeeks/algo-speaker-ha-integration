"""
Tests for Algo Speaker Home Assistant Integration
"""

import unittest
from unittest.mock import patch, MagicMock
import sys
import os

# Add the parent directory to the path so we can import our modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from algo_speaker_integration import AlgoSpeakerAPI


class TestAlgoSpeakerAPI(unittest.TestCase):
    """Test cases for AlgoSpeakerAPI class"""

    def setUp(self):
        """Set up test fixtures before each test method."""
        self.api = AlgoSpeakerAPI("192.168.1.100", "test_password")

    def test_init(self):
        """Test API initialization"""
        self.assertEqual(self.api.ip_address, "192.168.1.100")
        self.assertEqual(self.api.password, "test_password")
        self.assertEqual(self.api.base_url, "http://192.168.1.100")

    def test_generate_hmac_with_payload(self):
        """Test HMAC generation with payload"""
        hmac_key, nonce, timestamp = self.api._generate_hmac(
            "POST", "/api/controls/tone/start", "test_md5"
        )
        
        self.assertIsInstance(hmac_key, str)
        self.assertIsInstance(nonce, str)
        self.assertIsInstance(timestamp, str)
        self.assertEqual(len(hmac_key), 64)  # SHA-256 hex length

    def test_generate_hmac_without_payload(self):
        """Test HMAC generation without payload"""
        hmac_key, nonce, timestamp = self.api._generate_hmac(
            "GET", "/api/settings/device.info"
        )
        
        self.assertIsInstance(hmac_key, str)
        self.assertIsInstance(nonce, str)
        self.assertIsInstance(timestamp, str)
        self.assertEqual(len(hmac_key), 64)  # SHA-256 hex length

    @patch('algo_speaker_integration.requests.post')
    def test_play_tone_success(self, mock_post):
        """Test successful tone playback"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "Success"
        mock_post.return_value = mock_response

        success, response = self.api.play_tone("test.wav", False, 50)
        
        self.assertTrue(success)
        self.assertEqual(response, "Success")
        mock_post.assert_called_once()

    @patch('algo_speaker_integration.requests.post')
    def test_play_tone_failure(self, mock_post):
        """Test failed tone playback"""
        mock_post.side_effect = Exception("Connection error")

        success, response = self.api.play_tone("test.wav")
        
        self.assertFalse(success)
        self.assertEqual(response, "Connection error")

    @patch('algo_speaker_integration.requests.post')
    def test_stop_tone(self, mock_post):
        """Test stopping tone"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "Stopped"
        mock_post.return_value = mock_response

        success, response = self.api.stop_tone()
        
        self.assertTrue(success)
        self.assertEqual(response, "Stopped")

    @patch('algo_speaker_integration.requests.get')
    def test_get_device_info_success(self, mock_get):
        """Test successful device info retrieval"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"device.model": "8180", "device.version": "3.3.0"}
        mock_get.return_value = mock_response

        success, response = self.api.get_device_info()
        
        self.assertTrue(success)
        self.assertIsInstance(response, dict)
        self.assertEqual(response["device.model"], "8180")

    @patch('algo_speaker_integration.requests.get')
    def test_get_device_info_failure(self, mock_get):
        """Test failed device info retrieval"""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.text = "Not Found"
        mock_get.return_value = mock_response

        success, response = self.api.get_device_info()
        
        self.assertFalse(success)
        self.assertEqual(response, "Not Found")


if __name__ == '__main__':
    unittest.main()
