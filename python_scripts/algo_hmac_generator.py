"""
HMAC Generator for Algo Speaker API
This script generates the required HMAC authentication for Algo API calls
"""

import hashlib
import hmac
import time
import random
from datetime import datetime

def generate_hmac_auth(password, method, uri, content_md5="", content_type="application/json"):
    """
    Generate HMAC authentication for Algo API
    
    Args:
        password (str): API password (default: "algo")
        method (str): HTTP method (GET, POST, PUT, DELETE)
        uri (str): API endpoint URI
        content_md5 (str): MD5 hash of content (for POST/PUT requests)
        content_type (str): Content type (default: "application/json")
    
    Returns:
        dict: Authentication data including nonce, timestamp, and HMAC key
    """
    timestamp = str(int(time.time()))
    nonce = str(random.randint(100000, 999999))
    
    # Create HMAC input string
    if content_md5:
        hmac_input = f"{method}:{uri}:{content_md5}:{content_type}:{timestamp}:{nonce}"
    else:
        hmac_input = f"{method}:{uri}:{timestamp}:{nonce}"
    
    # Generate HMAC key
    hmac_key = hmac.new(
        password.encode('utf-8'),
        hmac_input.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    # Generate date header
    date_header = datetime.utcnow().strftime('%a, %d %b %Y %H:%M:%S GMT')
    
    return {
        'nonce': nonce,
        'timestamp': timestamp,
        'hmac_key': hmac_key,
        'date_header': date_header,
        'hmac_input': hmac_input
    }

def generate_content_md5(payload):
    """Generate MD5 hash for JSON payload"""
    import json
    json_str = json.dumps(payload, separators=(',', ':'))
    return hashlib.md5(json_str.encode('utf-8')).hexdigest()

# Example usage
if __name__ == "__main__":
    # Example for a GET request
    auth_data = generate_hmac_auth("algo", "GET", "/api/settings/device.info")
    print("GET Request Auth:")
    print(f"Nonce: {auth_data['nonce']}")
    print(f"HMAC Key: {auth_data['hmac_key']}")
    print(f"Date: {auth_data['date_header']}")
    print(f"Authorization: hmac admin:{auth_data['nonce']}:{auth_data['hmac_key']}")
    
    # Example for a POST request with payload
    payload = {"path": "page-notif.wav", "loop": False}
    content_md5 = generate_content_md5(payload)
    auth_data = generate_hmac_auth("algo", "POST", "/api/controls/tone/start", content_md5)
    print("\nPOST Request Auth:")
    print(f"Content-MD5: {content_md5}")
    print(f"Nonce: {auth_data['nonce']}")
    print(f"HMAC Key: {auth_data['hmac_key']}")
    print(f"Date: {auth_data['date_header']}")
    print(f"Authorization: hmac admin:{auth_data['nonce']}:{auth_data['hmac_key']}")
