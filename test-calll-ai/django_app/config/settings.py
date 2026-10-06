import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', 'django-insecure-default-key-change-in-prod')

DEBUG = os.getenv('DEBUG', '1') == '1'

ALLOWED_HOSTS = ['*']

CSRF_TRUSTED_ORIGINS = [
    'https://app.localhost',
    'https://*.localhost',
    'https://*.nip.io',
    'https://169.58.32.179.nip.io',
    'https://app.169.58.32.179.nip.io',
    'https://employee.169.58.32.179.nip.io',
    'http://employee.169.58.32.179.nip.io',
    'http://169.58.32.179.nip.io',
    'http://app.169.58.32.179.nip.io',
    'https://localhost',
    'http://localhost',
    'http://localhost:8000',
    'http://localhost:8080',
    'http://127.0.0.1:8000',
    'http://127.0.0.1:8080',
    'https://127.0.0.1',
]

SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
USE_X_FORWARDED_HOST = True


INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'drf_spectacular',
    'knowledge.apps.KnowledgeConfig',
    'agents.apps.AgentsConfig',
    'call_center.apps.CallCenterConfig',
    'telephony.apps.TelephonyConfig',
    'crm.apps.CrmConfig',
    'billing.apps.BillingConfig',
    'partners.apps.PartnersConfig',
    'developer.apps.DeveloperConfig',
    'voice_assistant.apps.VoiceAssistantConfig',
]

MIDDLEWARE = [
    'config.cors_middleware.SimpleCorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'
ASGI_APPLICATION = 'config.asgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('POSTGRES_DB', 'voice_db'),
        'USER': os.getenv('POSTGRES_USER', 'voice_user'),
        'PASSWORD': os.getenv('POSTGRES_PASSWORD', 'voice_password_123'),
        'HOST': os.getenv('POSTGRES_HOST', 'postgres'),
        'PORT': os.getenv('POSTGRES_PORT', '5432'),
        'CONN_MAX_AGE': int(os.getenv('DATABASE_CONN_MAX_AGE', '60')),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/login/'

LANGUAGE_CODE = 'ar'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedStaticFilesStorage",
    },
}

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Redis
REDIS_URL = os.getenv('REDIS_URL', 'redis://redis:6379/0')

# LiveKit
LIVEKIT_URL = os.getenv('LIVEKIT_URL', 'wss://livekit.localhost')
LIVEKIT_INTERNAL_URL = os.getenv('LIVEKIT_INTERNAL_URL', 'ws://livekit:7880')
LIVEKIT_API_KEY = os.getenv('LIVEKIT_API_KEY', 'devkey')
LIVEKIT_API_SECRET = os.getenv('LIVEKIT_API_SECRET', 'secretkey1234567890abcdef')

# Centrifugo
CENTRIFUGO_HTTP_API_URL = os.getenv('CENTRIFUGO_HTTP_API_URL', 'http://centrifugo:8000/api')
CENTRIFUGO_API_KEY = os.getenv('CENTRIFUGO_API_KEY', 'centrifugo_api_key_1234567890')
CENTRIFUGO_SECRET = os.getenv('CENTRIFUGO_SECRET', 'centrifugo_secret_key_1234567890')
CENTRIFUGO_WS_URL = os.getenv('CENTRIFUGO_WS_URL', 'wss://centrifugo.localhost/connection/websocket')

# Google Gemini
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')

# Internal Agent Service Authentication Key
INTERNAL_API_KEY = os.getenv('INTERNAL_API_KEY', 'voice-internal-secret-token-key-12345')

# Host IP
EXTERNAL_IP = os.getenv('EXTERNAL_IP', '169.58.32.179')

# MinIO & Call Recordings Storage
MINIO_ENDPOINT = os.getenv('MINIO_ENDPOINT', 'http://minio:9000')
MINIO_EXTERNAL_URL = os.getenv('MINIO_EXTERNAL_URL', f"https://minio.{EXTERNAL_IP}.nip.io")
MINIO_ACCESS_KEY = os.getenv('MINIO_ROOT_USER', os.getenv('MINIO_ACCESS_KEY', 'minioadmin'))
MINIO_SECRET_KEY = os.getenv('MINIO_ROOT_PASSWORD', os.getenv('MINIO_SECRET_KEY', 'minioadmin123'))
MINIO_BUCKET_NAME = os.getenv('MINIO_BUCKET_NAME', 'call-recordings')

# Django REST Framework & OpenAPI Documentation (drf-spectacular + Scalar)
REST_FRAMEWORK = {
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'DEFAULT_AUTHENTICATION_CLASSES': [],
}

SPECTACULAR_SETTINGS = {
    'TITLE': 'منصة المساعد الصوتي والذكاء الاصطناعي (Smart Voice AI)',
    'DESCRIPTION': 'توثيق واجهات برمجة التطبيقات للمطورين وحلول الشركاء (SaaS & WebRTC Calling)',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'COMPONENT_SPLIT_REQUEST': True,
    'SECURITY': [
        {'ApiKeyAuth': []},
        {'PartnerKey': []},
        {'BearerAuth': []},
    ],
    'APPEND_COMPONENTS': {
        'securitySchemes': {
            'PartnerKey': {
                'type': 'apiKey',
                'in': 'header',
                'name': 'X-Partner-Key',
                'description': 'مفتاح الشريك السري (sk_live_prt_...)',
            },
            'ApiKeyAuth': {
                'type': 'apiKey',
                'in': 'header',
                'name': 'X-API-Key',
                'description': 'مفتاح الـ API الشخصي (sk_live_usr_... أو sk_live_ptnr_...)',
            },
            'BearerAuth': {
                'type': 'http',
                'scheme': 'bearer',
                'bearerFormat': 'JWT',
                'description': 'Bearer Token للوصول المصرح',
            },
        }
    },
}
