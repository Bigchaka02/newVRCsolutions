"""Email. SMTP is live (services.send_email logs instead when SMTP_HOST is
blank). A transactional provider (templates, deliverability, open tracking)
is a placeholder; the old site's addresses were hello@, orders@,
compliance@, privacy@ and legal@vrcsolutions.co."""

from .base import Integration, register

SMTP = register(Integration(
    "email.smtp", "SMTP email",
    "Order confirmations, contact-form routing, shipping notices.",
    "Live site contact addresses", ("smtp_host",), implemented=True,
))
TRANSACTIONAL = register(Integration(
    "email.transactional", "Transactional email provider",
    "Branded templates and delivery tracking, replacing plain SMTP.",
    "Typical WooCommerce setup (WP Mail SMTP or similar)",
    ("email_provider", "email_api_key"),
))
