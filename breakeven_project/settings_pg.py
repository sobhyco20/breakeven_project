from .settings import *

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "breakeven",
        "USER": "postgres",
        "PASSWORD": "StrongPass_123!",
        "HOST": "127.0.0.1",
        "PORT": "5432",
    }
}
