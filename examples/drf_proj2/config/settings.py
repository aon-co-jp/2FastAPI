SECRET_KEY = "test"
DEBUG = False
ALLOWED_HOSTS = ["*"]
ROOT_URLCONF = "config.urls"
INSTALLED_APPS = ["rest_framework"]
USE_TZ = True
REST_FRAMEWORK = {"DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"], "UNAUTHENTICATED_USER": None}
