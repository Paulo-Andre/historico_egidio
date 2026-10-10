from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)


def _read_runtime_secret(env_name, filename):
    value = os.getenv(env_name, "").strip()
    if value:
        return value

    secret_path = DATA_DIR / filename
    if secret_path.exists():
        return secret_path.read_text(encoding="utf-8").strip()

    return ""


SECRET_KEY = _read_runtime_secret(
    "DJANGO_SECRET_KEY",
    ".django_secret_key",
)
DEBUG = os.getenv("DJANGO_DEBUG", "0") == "1"
if not SECRET_KEY:
    raise RuntimeError(
        "Chave Django não disponível no ambiente nem no arquivo persistente."
    )

DOCUMENT_SIGNING_KEY = _read_runtime_secret(
    "DOCUMENT_SIGNING_KEY",
    ".document_signing_key",
)
if not DOCUMENT_SIGNING_KEY:
    raise RuntimeError(
        "Chave de assinatura não disponível no ambiente nem no arquivo persistente."
    )

ALLOWED_HOSTS = [
    x.strip()
    for x in os.getenv(
        "DJANGO_ALLOWED_HOSTS",
        "127.0.0.1,localhost,192.168.1.17",
    ).split(",")
    if x.strip()
]

INSTALLED_APPS = [
    "django.contrib.admin", "django.contrib.auth", "django.contrib.contenttypes",
    "django.contrib.sessions", "django.contrib.messages", "django.contrib.staticfiles",
    "historico",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "historico.middleware.SecurityAuditMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
ROOT_URLCONF = "config.urls"
TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [], "APP_DIRS": True,
    "OPTIONS": {"context_processors": [
        "django.template.context_processors.request",
        "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages",
    ]},
}]
WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": DATA_DIR / "historico.sqlite3",
        "OPTIONS": {
            # Importações de ATA escrevem milhares de registros. Um timeout
            # maior evita falhas transitórias "database is locked" quando
            # outro worker estiver encerrando uma escrita curta.
            "timeout": 60,
        },
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 12},
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]
LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Sao_Paulo"
USE_I18N = True
USE_TZ = True
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
LOGIN_URL = "/admin/login/"


# Segurança de sessão/CSRF. Em acesso local por HTTP mantenha
# DJANGO_SECURE_COOKIES=0; atrás de HTTPS/Cloudflare use =1.
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
SECURE_COOKIES = os.getenv("DJANGO_SECURE_COOKIES", "0") == "1"
SESSION_COOKIE_SECURE = SECURE_COOKIES
CSRF_COOKIE_SECURE = SECURE_COOKIES
SECURE_SSL_REDIRECT = os.getenv("DJANGO_SECURE_SSL_REDIRECT", "0") == "1"
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_HSTS_SECONDS = int(os.getenv("DJANGO_HSTS_SECONDS", "0"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = SECURE_HSTS_SECONDS > 0
SECURE_HSTS_PRELOAD = False
X_FRAME_OPTIONS = "DENY"

LOGIN_URL = "/admin/login/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/admin/login/"

# Limites defensivos para uploads e formulários.
DATA_UPLOAD_MAX_MEMORY_SIZE = 30 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024
DATA_UPLOAD_MAX_NUMBER_FIELDS = 5000

CSRF_TRUSTED_ORIGINS = [
    origem.strip()
    for origem in os.getenv("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",")
    if origem.strip()
]
SESSION_COOKIE_AGE = int(os.getenv("DJANGO_SESSION_AGE", "3600"))
SESSION_SAVE_EVERY_REQUEST = True
