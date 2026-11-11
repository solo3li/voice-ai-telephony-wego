# config package
import re
import django.http.request

# Allow hostnames with underscores like 'voice_django' in Docker Compose
django.http.request.host_validation_re = re.compile(
    r"^([a-z0-9_.-]+|\[[a-f0-9]*:[a-f0-9:]+\])(?::([0-9]+))?$",
    re.IGNORECASE
)

