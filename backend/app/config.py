"""Settings loaded from environment / .env, validated once at import."""

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    database_url: str = "sqlite:///./vrc.db"
    cors_origins: str = "http://localhost:8000"

    admin_token: str = "change-me-before-deploying"
    ip_hash_salt: str = "change-me-too"

    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    mail_from: str = "orders@vrcsolutions.co"

    venmo_handle: str = ""
    cashapp_handle: str = ""
    btc_address: str = ""
    eth_address: str = ""
    usdc_address: str = ""

    # ---- Integrations (placeholders until the original backend is supplied) ----
    # Leave blank to keep an integration in placeholder mode. See app/integrations/.
    card_processor: str = ""          # e.g. the high-risk processor the old site used
    card_api_key: str = ""
    card_webhook_secret: str = ""
    crypto_processor: str = ""        # blank = manual wallet addresses above
    crypto_api_key: str = ""
    crypto_webhook_secret: str = ""
    shipping_provider: str = ""       # e.g. ShipStation, Shippo, EasyPost, Pirate Ship
    shipping_api_key: str = ""
    shipping_webhook_secret: str = ""
    email_provider: str = ""          # blank = SMTP settings above
    email_api_key: str = ""
    woo_url: str = ""                 # old WordPress site, for one-time data import
    woo_consumer_key: str = ""
    woo_consumer_secret: str = ""
    analytics_id: str = ""
    newsletter_provider: str = ""
    newsletter_api_key: str = ""

    # Commercial rules live here, not in the request handler, so the storefront
    # and the API can never disagree about what an order costs.
    free_shipping_threshold: float = 105.00
    flat_shipping: float = 9.95
    promo_code: str = "FIRST15"
    promo_percent: int = 15
    max_qty_per_line: int = 99

    # Single-process mode: the API also serves the built site from public/.
    # Handy on one small VPS. Leave off when the site is on a CDN.
    rate_limit_enabled: bool = True
    serve_static: bool = False
    static_dir: str = "../public"

    @property
    def origins(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() in {"production", "prod"}


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
