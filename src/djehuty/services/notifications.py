"""Templated e-mail notifications, lifted AS-IS from the legacy wsgi.py.

The EmailInterface instance is passed in by the caller: ui.py configures the
SMTP settings on the legacy server's instance, and the dispatcher shares that
same instance with the FastAPI app (app.state.email). A missing or
unconfigured interface makes every send a logged no-op, like legacy.
"""

import logging
import os

from jinja2 import Environment, FileSystemLoader

from djehuty.utils.convenience import value_or_none
from djehuty.web import email_handler
from djehuty.web.config import config

_log = logging.getLogger(__name__)

_TEMPLATES_PATH = os.path.join(
    os.path.dirname(email_handler.__file__), "resources", "html_templates"
)
_jinja = Environment(loader=FileSystemLoader(_TEMPLATES_PATH), autoescape=True)


def render_email_templates(template_name, **context):
    """Render a plaintext and an HTML body for sending in an e-mail."""
    html_template = _jinja.get_template(f"{template_name}.html")
    text_template = _jinja.get_template(f"{template_name}.txt")
    parameters = {"base_url": config.base_url, "site_name": config.site_name}
    html_response = html_template.render({**context, **parameters})
    text_response = text_template.render({**context, **parameters})
    return text_response, html_response


def send_templated_email(db, email, email_addresses, subject, template_name, **context):
    """Send an e-mail according to a template to the list of EMAIL_ADDRESSES."""
    if not email_addresses or email is None or not email.is_properly_configured():
        return False

    failure_count = 0
    for email_address in email_addresses:
        if not db.may_receive_email_notifications(email_address):
            _log.info("Did not send e-mail to '%s' due to settings.", email_address)
            continue

        text, html = render_email_templates(
            f"email/{template_name}", recipient_email=email_address, **context
        )
        if not email.send_email(email_address, subject, text, html):
            failure_count += 1

    if failure_count > 0:
        _log.info(
            "Failed to send e-mail to %d out of %d address(es): %s",
            failure_count,
            len(email_addresses),
            subject,
        )
        return False

    _log.info("Sent e-mail to %d address(es): %s", len(email_addresses), subject)
    return True


def send_email_to_reviewers(db, email, subject, template_name, **context):
    """Send an e-mail to all accounts configured with 'may_review' privileges."""
    addresses = db.reviewer_email_addresses()
    account_email = context.get("account_email")
    if account_email is not None:
        domain = value_or_none(account_email.rsplit("@", 1), 1)
        addresses += db.institutional_reviewer_email_addresses(domain)
        addresses = list(set(addresses))
    return send_templated_email(db, email, addresses, subject, template_name, **context)
