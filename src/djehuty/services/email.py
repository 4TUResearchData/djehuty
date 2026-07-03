"""Transactional e-mail for the HTTP API.

Standalone port of the legacy e-mail helpers (``__send_templated_email`` and
friends). It renders the shared e-mail templates and sends through the
configured mail server. A missing or misconfigured mail server short-circuits
to a no-op, so callers never fail because e-mail is unavailable.
"""

import logging
import os

from jinja2 import Environment, FileSystemLoader

from djehuty.utils.convenience import value_or_none
from djehuty.web import email_handler
from djehuty.web.config import config

logger = logging.getLogger(__name__)

_templates_path = os.path.join(
    os.path.dirname(email_handler.__file__), "resources", "html_templates"
)
_jinja = Environment(loader=FileSystemLoader(_templates_path), autoescape=True)


def _render(template_name, **context):
    """Render the plaintext and HTML bodies for an e-mail template."""
    html_template = _jinja.get_template(f"email/{template_name}.html")
    text_template = _jinja.get_template(f"email/{template_name}.txt")
    parameters = {"base_url": config.base_url, "site_name": config.site_name}
    return (
        text_template.render({**context, **parameters}),
        html_template.render({**context, **parameters}),
    )


def send_templated_email(db, email_addresses, subject, template_name, **context):
    """Send a templated e-mail to each address, honouring per-account settings."""
    email = getattr(config, "email_interface", None)
    if not email_addresses or email is None or not email.is_properly_configured():
        return False

    failure_count = 0
    for email_address in email_addresses:
        if not db.may_receive_email_notifications(email_address):
            logger.info("Did not send e-mail to '%s' due to settings.", email_address)
            continue
        text, html = _render(template_name, recipient_email=email_address, **context)
        if not email.send_email(email_address, subject, text, html):
            failure_count += 1

    if failure_count > 0:
        logger.info(
            "Failed to send e-mail to %d out of %d address(es): %s",
            failure_count,
            len(email_addresses),
            subject,
        )
        return False

    logger.info("Sent e-mail to %d address(es): %s", len(email_addresses), subject)
    return True


def send_email_to_reviewers(db, subject, template_name, account_email=None, **context):
    """Send a templated e-mail to reviewer accounts, plus institutional reviewers."""
    addresses = db.reviewer_email_addresses()
    if account_email is not None:
        domain = value_or_none(account_email.rsplit("@", 1), 1)
        addresses += db.institutional_reviewer_email_addresses(domain)
        addresses = list(set(addresses))
    return send_templated_email(
        db, addresses, subject, template_name, account_email=account_email, **context
    )


def send_email_to_quota_reviewers(db, subject, template_name, **context):
    """Send a templated e-mail to accounts that review quota requests."""
    addresses = db.quota_reviewer_email_addresses()
    return send_templated_email(db, addresses, subject, template_name, **context)
