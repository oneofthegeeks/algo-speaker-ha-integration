"""
Algo Speaker Integration for Home Assistant
Provides HMAC authentication and API communication for Algo IP speakers
"""

import hashlib
import hmac
import json
import random
import time
from datetime import datetime, timezone

import requests


class AlgoSpeakerAPI:
    def __init__(self, ip_address, password="algo"):
        self.ip_address = ip_address
        self.password = password
        self.base_url = f"http://{ip_address}"

    def _generate_hmac(
        self,
        method,
        uri,
        content_md5="",
        content_type="application/json",
        timestamp=None,
        nonce=None,
    ):
        """Generate HMAC for Algo API authentication"""
        if timestamp is None:
            timestamp = str(int(time.time()))
        if nonce is None:
            nonce = str(random.randint(100000, 999999))

        # Create HMAC input string
        if content_md5:
            hmac_input = (
                f"{method}:{uri}:{content_md5}:{content_type}:{timestamp}:{nonce}"
            )
        else:
            hmac_input = f"{method}:{uri}:{timestamp}:{nonce}"

        # Generate HMAC key
        hmac_key = hmac.new(
            self.password.encode("utf-8"), hmac_input.encode("utf-8"), hashlib.sha256
        ).hexdigest()

        return hmac_key, nonce, timestamp

    def _get_headers(self, method, uri, payload=None):
        """Generate headers for API request"""
        timestamp = str(int(time.time()))
        nonce = str(random.randint(100000, 999999))

        if payload:
            # For requests with JSON payload
            content_md5 = hashlib.md5(
                json.dumps(payload, separators=(",", ":")).encode("utf-8")
            ).hexdigest()
            hmac_key, nonce, timestamp = self._generate_hmac(method, uri, content_md5)

            headers = {
                "Content-Type": "application/json",
                "Content-MD5": content_md5,
                "Authorization": f"hmac admin:{nonce}:{hmac_key}",
                "Date": datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT"),
            }
        else:
            # For requests without payload
            hmac_key, nonce, timestamp = self._generate_hmac(method, uri)

            headers = {
                "Authorization": f"hmac admin:{nonce}:{hmac_key}",
                "Date": datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT"),
            }

        return headers

    def play_tone(self, path, loop=False, volume=None):
        """Play a tone/announcement on the speaker"""
        payload = {"path": path, "loop": loop}
        if volume is not None:
            payload["volume"] = volume

        headers = self._get_headers("POST", "/api/controls/tone/start", payload)

        try:
            response = requests.post(
                f"{self.base_url}/api/controls/tone/start",
                headers=headers,
                json=payload,
                timeout=10,
            )
            return response.status_code == 200, response.text
        except Exception as e:
            return False, str(e)

    def stop_tone(self):
        """Stop current tone/announcement"""
        headers = self._get_headers("POST", "/api/controls/tone/stop")

        try:
            response = requests.post(
                f"{self.base_url}/api/controls/tone/stop", headers=headers, timeout=10
            )
            return response.status_code == 200, response.text
        except Exception as e:
            return False, str(e)

    def start_strobe(self, pattern=1, color1="red", color2="blue", ledlvl="100"):
        """Start strobe light (if supported by speaker model)"""
        payload = {
            "pattern": pattern,
            "color1": color1,
            "color2": color2,
            "ledlvl": ledlvl,
        }

        headers = self._get_headers("POST", "/api/controls/strobe/start", payload)

        try:
            response = requests.post(
                f"{self.base_url}/api/controls/strobe/start",
                headers=headers,
                json=payload,
                timeout=10,
            )
            return response.status_code == 200, response.text
        except Exception as e:
            return False, str(e)

    def stop_strobe(self):
        """Stop strobe light"""
        headers = self._get_headers("POST", "/api/controls/strobe/stop")

        try:
            response = requests.post(
                f"{self.base_url}/api/controls/strobe/stop", headers=headers, timeout=10
            )
            return response.status_code == 200, response.text
        except Exception as e:
            return False, str(e)

    def get_device_info(self):
        """Get device information and status"""
        headers = self._get_headers("GET", "/api/settings/device.info")

        try:
            response = requests.get(
                f"{self.base_url}/api/settings/device.info", headers=headers, timeout=10
            )
            if response.status_code == 200:
                return True, response.json()
            else:
                return False, response.text
        except Exception as e:
            return False, str(e)

    def get_audio_volume(self):
        """Get current audio volume"""
        headers = self._get_headers("GET", "/api/settings/audio.page.vol")

        try:
            response = requests.get(
                f"{self.base_url}/api/settings/audio.page.vol",
                headers=headers,
                timeout=10,
            )
            if response.status_code == 200:
                return True, response.json()
            else:
                return False, response.text
        except Exception as e:
            return False, str(e)

    def set_audio_volume(self, volume):
        """Set audio volume (PUT request for permanent setting)"""
        payload = {"audio.page.vol": volume}
        headers = self._get_headers("PUT", "/api/settings/audio.page.vol", payload)

        try:
            response = requests.put(
                f"{self.base_url}/api/settings/audio.page.vol",
                headers=headers,
                json=payload,
                timeout=10,
            )
            return response.status_code == 200, response.text
        except Exception as e:
            return False, str(e)
