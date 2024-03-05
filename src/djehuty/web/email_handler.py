"""This module provides the functionality to send e-mails."""

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

class EmailInterface:
    """This class implements sending e-mail and e-mail templates."""

    def __init__ (self):
        self.smtp_server = None
        self.from_address = None
        self.smtp_username = None
        self.smtp_password = None
        self.smtp_port = 587
        self.do_starttls = True
        self.log = logging.getLogger(__name__)
        self.subject_prefix = None

    def is_properly_configured (self):
        """Procedure to bail early on a misconfigured instance of this class."""
        return (self.smtp_server is not None and
                self.from_address is not None and
                self.smtp_username is not None and
                self.smtp_password is not None)

    def send_email (self, recipient, subject, plaintext, html):
        """Procedure to send an email."""

        if not self.is_properly_configured ():
            self.log.error ("E-mail server not properly configured.")
            return False

        message = MIMEMultipart ("alternative")
        message["From"] = self.from_address
        message["To"] = recipient
        if self.subject_prefix:
            message["Subject"] = f"{self.subject_prefix} {subject}"
        else:
            message["Subject"] = subject

        message.attach (MIMEText (plaintext, "plain"))
        message.attach (MIMEText (html, "html"))

        try:
            connection = smtplib.SMTP (self.smtp_server, self.smtp_port, timeout=10)
        except (smtplib.SMTPConnectError, smtplib.SMTPException, ConnectionRefusedError) as error:
            self.log.error ("Connecting to the e-mail server failed: %s", error)
            return False

        connection.ehlo()
        if self.do_starttls:
            connection.starttls ()
        else:
            self.log.error ("The e-mail interface hasn't been tested without STARTTLS.")
            self.log.error ("Please review the code before continuing.")
            return False

        try:
            connection.login (self.smtp_username, self.smtp_password)
        except smtplib.SMTPAuthenticationError:
            self.log.error ("Wrong credentials for authenticating to the e-mail server.")
            return False
        except (smtplib.SMTPHeloError,
                smtplib.SMTPNotSupportedError, smtplib.SMTPException) as error:
            self.log.error ("Authenticating to the e-mail server failed: %s", error)
            return False

        try:
            connection.sendmail (self.from_address, recipient, message.as_string())
        except (smtplib.SMTPRecipientsRefused, smtplib.SMTPHeloError, smtplib.SMTPSenderRefused,
                smtplib.SMTPDataError, smtplib.SMTPNotSupportedError) as error:
            self.log.error ("Sending e-mail failed: %s", error)
            return False

        connection.close()
        return True
