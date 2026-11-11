"""
ASGI config for voice_service project.

It exposes the ASGI callable as a module-level variable named ``application``.
"""

import os
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import re
import django.http.request
django.http.request.host_validation_re = re.compile(
    r"^([a-z0-9_.-]+|\[[a-f0-9]*:[a-f0-9:]+\])(?::([0-9]+))?$",
    re.IGNORECASE
)

application = get_asgi_application()
