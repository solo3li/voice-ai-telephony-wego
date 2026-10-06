import os
import logging
from dotenv import load_dotenv

load_dotenv()

# Logging Configuration
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("VoiceAgentDaemon")

# Network & Service Endpoints
LIVEKIT_INTERNAL_URL = os.getenv("LIVEKIT_INTERNAL_URL", "ws://livekit:7880")
LIVEKIT_API_KEY = os.getenv("LIVEKIT_API_KEY", "devkey")
LIVEKIT_API_SECRET = os.getenv("LIVEKIT_API_SECRET", "secretkey1234567890abcdef")
CENTRIFUGO_HTTP_API_URL = os.getenv("CENTRIFUGO_HTTP_API_URL", "http://centrifugo:8000/api")
CENTRIFUGO_API_KEY = os.getenv("CENTRIFUGO_API_KEY", "centrifugo_api_key_1234567890")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
DJANGO_API_URL = os.getenv("DJANGO_API_URL", "http://django:8000")
INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY", "voice-internal-secret-token-key-12345")
INNGEST_EVENT_URL = os.getenv("INNGEST_EVENT_URL", "http://inngest:8288/e/key")
WAZO_SIP_HOST = os.getenv("WAZO_SIP_HOST", os.getenv("EXTERNAL_IP", "127.0.0.1"))
WAZO_SIP_PORT = int(os.getenv("WAZO_SIP_PORT", "5070"))

# Audio Pipeline Standard Constants
IN_SAMPLE_RATE = 16000          # Gemini input sample rate
IN_NUM_CHANNELS = 1
IN_CHUNK_SIZE = 1280            # 40ms at 16kHz 16-bit mono (16000 * 0.040 * 2)

# NOTE: Gemini Live API outputs PCM at 24kHz. We upsample to 48kHz in the pipeline
# so that LiveKit SIP receives native 48kHz PCM (expected_pcm_hz: 48000) and avoids
# its internal resampler, which was causing mixer restarts and dropped samples.
GEMINI_OUT_SAMPLE_RATE = 24000  # Raw Gemini audio output rate (fixed by API)
OUT_SAMPLE_RATE = 48000         # Upsampled rate: native to LiveKit SIP & WebRTC
OUT_NUM_CHANNELS = 1
OUT_FRAME_SAMPLES = 960         # 20ms at 48kHz (48000 * 0.020)
OUT_FRAME_BYTES = 1920          # 960 samples * 2 bytes (16-bit PCM)
AUDIO_FRAME_INTERVAL = 0.020    # Exact 20ms between 20ms frames (drift-compensated clock)
AUDIO_SILENCE_THRESHOLD = 0.25  # Seconds of silence after turn_complete before marking agent stopped speaking

# Default Gemini Models
GEMINI_LIVE_MODEL = os.getenv("GEMINI_LIVE_MODEL", "gemini-3.8-live")
GEMINI_FLASH_MODEL = os.getenv("GEMINI_FLASH_MODEL", "gemini-3.8-flash")
