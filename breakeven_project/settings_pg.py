from .settings import *
import os
from urllib.parse import urlparse

DATABASE_URL = (os.getenv("DATABASE_URL") or "").strip()

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is missing. Set it in Render Environment Variables.")

u = urlparse(DATABASE_URL)
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": u.path.lstrip("/"),
        "USER": u.username,
        "PASSWORD": u.password,
        "HOST": u.hostname,
        "PORT": u.port or 5432,
        "CONN_MAX_AGE": 60,
    }
}
