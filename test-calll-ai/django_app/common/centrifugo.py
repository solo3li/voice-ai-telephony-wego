"""Centralized Centrifugo publishing service for real-time notifications."""
import logging
import requests
from django.conf import settings

logger = logging.getLogger("CentrifugoClient")


def publish_to_centrifugo(channel: str, data: dict, timeout: float = 2.0) -> bool:
    """
    Publish real-time notification to a Centrifugo channel.
    Returns True if successfully published, False otherwise.
    """
    if not channel or not data:
        return False

    api_url = getattr(settings, 'CENTRIFUGO_HTTP_API_URL', 'http://centrifugo:8000/api')
    api_key = getattr(settings, 'CENTRIFUGO_API_KEY', 'centrifugo_api_key_1234567890')

    url = f"{api_url}/publish"
    headers = {
        "Authorization": f"apikey {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "channel": channel,
        "data": data,
    }

    try:
        res = requests.post(url, json=payload, headers=headers, timeout=timeout)
        if res.status_code == 200:
            return True
        logger.error(f"Centrifugo publish error for channel '{channel}' ({res.status_code}): {res.text}")
        return False
    except Exception as e:
        logger.error(f"Failed to publish to Centrifugo channel '{channel}': {e}")
        return False
