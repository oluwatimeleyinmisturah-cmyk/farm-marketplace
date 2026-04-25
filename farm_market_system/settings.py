from pathlib import Path
from decouple import config
import dj_database_url
import os

BASE_DIR = Path(__file__).resolve().parent.parent

# ─────────────────────────────
# SECURITY
# ─────────────────────────────
SECRET_KEY = config('SECRET_KEY')

DEBUG = config('DEBUG', default=False, cast=bool)

ALLOWED_HOSTS = ['.onrender.com', 'localhost', '127.0.0.1']

CSRF_TRUSTED_ORIGINS = [
    'https://*.onrender.com'
]

# ─────────────────────────────
# APPLICATIONS
# ─────────────────────────────
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
    'marketplace.apps.MarketplaceConfig',
]


# ─────────────────────────────
# MIDDLEWARE
# ─────────────────────────────
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',

    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]


# ─────────────────────────────
# URL / WSGI
# ─────────────────────────────
ROOT_URLCONF = 'farm_market_system.urls'
WSGI_APPLICATION = 'farm_market_system.wsgi.application'


# ─────────────────────────────
# DATABASE
# ─────────────────────────────
DATABASES = {
    'default': dj_database_url.config(
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
        conn_max_age=600
    )
}

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.template.context_processors.csrf',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

# ─────────────────────────────
# STATIC FILES
# ─────────────────────────────
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

STATICFILES_DIRS = [BASE_DIR / 'marketplace' / 'static']

STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'


# ─────────────────────────────
# MEDIA FILES
# ─────────────────────────────
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'


# ─────────────────────────────
# DEFAULT PRIMARY KEY
# ─────────────────────────────
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# ─────────────────────────────
# AUTH REDIRECTS
# ─────────────────────────────
LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'home'
LOGOUT_REDIRECT_URL = 'login'


# ─────────────────────────────
# EMAIL (GMAIL SMTP)
# ─────────────────────────────
EMAIL_BACKEND       = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST          = 'smtp.gmail.com'
EMAIL_PORT          = 587
EMAIL_USE_TLS       = True
EMAIL_HOST_USER     = 'thesanniolawales@gmail.com'
EMAIL_HOST_PASSWORD = 'galkgblvbjxianmn'
DEFAULT_FROM_EMAIL  = f'Farm Market Africa <{EMAIL_HOST_USER}>'

CONTACT_EMAIL = 'thesanniolawales@gmail.com'


# ─────────────────────────────
# PAYSTACK
# ─────────────────────────────
PAYSTACK_PUBLIC_KEY = "pk_test_53737f1a57dac07a9d385fd8f4a7a3b82b1bf861"
PAYSTACK_SECRET_KEY = "sk_test_f488b8a3c3af6b3bd6fab7e3982f6f5dc9b3de05"