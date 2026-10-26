import os
import secrets
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured


BASE_DIR = Path(__file__).resolve().parent.parent
for line in (BASE_DIR / ".env").read_text().splitlines() if (BASE_DIR / ".env").exists() else []:
    if line.strip() and not line.lstrip().startswith("#") and "=" in line:
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))

DEBUG = os.getenv("DEBUG", "true").lower() == "true"
SECRET_KEY = os.getenv("SECRET_KEY", "")
if not SECRET_KEY:
    if not DEBUG:
        raise ImproperlyConfigured("部署环境必须设置 SECRET_KEY")
    secret_file = BASE_DIR / ".local-secret"
    if not secret_file.exists():
        try:
            with secret_file.open("x") as secret_stream:
                secret_stream.write(secrets.token_urlsafe(64))
            secret_file.chmod(0o600)
        except FileExistsError:
            pass
    SECRET_KEY = secret_file.read_text().strip()

ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "127.0.0.1,localhost,[::1]").split(",")
CSRF_TRUSTED_ORIGINS = [origin for origin in os.getenv("CSRF_TRUSTED_ORIGINS", "").split(",") if origin]
INSTALLED_APPS = [
    "django.contrib.admin", "django.contrib.auth", "django.contrib.contenttypes",
    "django.contrib.sessions", "django.contrib.messages", "django.contrib.staticfiles", "core",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware", "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware", "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware", "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware", "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
ROOT_URLCONF = "config.urls"
TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates", "DIRS": [BASE_DIR / "templates"],
    "APP_DIRS": True, "OPTIONS": {"context_processors": [
        "django.template.context_processors.request", "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages",
    ]},
}]
WSGI_APPLICATION = "config.wsgi.application"
if os.getenv("DB_ENGINE", "sqlite") == "mysql":
    import pymysql

    pymysql.install_as_MySQLdb()
    DATABASES = {"default": {
        "ENGINE": "django.db.backends.mysql", "NAME": os.getenv("DB_NAME", "testchain"),
        "USER": os.environ["DB_USER"], "PASSWORD": os.environ["DB_PASSWORD"],
        "HOST": os.getenv("DB_HOST", "127.0.0.1"), "PORT": os.getenv("DB_PORT", "3306"),
        "OPTIONS": {"charset": "utf8mb4", "init_command": "SET sql_mode='STRICT_TRANS_TABLES'"},
        "CONN_MAX_AGE": 60,
    }}
else:
    DATABASES = {"default": {
        "ENGINE": "django.db.backends.sqlite3", "NAME": os.getenv("SQLITE_PATH", str(BASE_DIR / "db.sqlite3")),
        "OPTIONS": {"timeout": 30},
    }}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
LANGUAGE_CODE = "zh-hans"
TIME_ZONE = "Asia/Shanghai"
USE_I18N = True
USE_TZ = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "dashboard"
LOGOUT_REDIRECT_URL = "login"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_AGE = 43200
SESSION_COOKIE_SAMESITE = "Lax"
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SECURE_SSL_REDIRECT = os.getenv("SECURE_SSL_REDIRECT", "false").lower() == "true"
SECURE_REDIRECT_EXEMPT = [r"^health/$"]
if os.getenv("TRUST_PROXY", "false").lower() == "true":
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = os.getenv("COOKIE_SECURE", "false" if DEBUG else "true").lower() == "true"
CSRF_COOKIE_SECURE = SESSION_COOKIE_SECURE
SECURE_HSTS_SECONDS = 31536000 if SECURE_SSL_REDIRECT else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = SECURE_SSL_REDIRECT
SECURE_HSTS_PRELOAD = SECURE_SSL_REDIRECT
DATA_UPLOAD_MAX_MEMORY_SIZE = 11 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024
REPORT_MAX_BYTES = 10 * 1024 * 1024
ALLOW_REGISTRATION = os.getenv("ALLOW_REGISTRATION", "true").lower() == "true"
CHAIN_DIFFICULTY = 3
LOGGING = {"version": 1, "disable_existing_loggers": False, "handlers": {
    "console": {"class": "logging.StreamHandler"},
}, "root": {"handlers": ["console"], "level": "INFO"}}
