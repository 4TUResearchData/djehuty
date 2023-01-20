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

    def __is_properly_configured (self):
        """Procedure to bail early on a misconfigured instance of this class."""
        return (self.smtp_server is not None and
                self.from_address is not None and
                self.smtp_username is not None and
                self.smtp_password is not None)

    def send_email (self, to, subject, plaintext, html):
        """Procedure to send an email."""

        if not self.__is_properly_configured ():
            logging.error ("The e-mail interface seems to be misconfigured.")
            logging.error ("Refusing to continue.")
            return False

        message = MIMEMultipart ("alternative")
        message["From"] = self.from_address
        message["To"] = to
        message["Subject"] = subject

        message.attach (MIMEText (plaintext, "plain"))
        message.attach (MIMEText (html, "html"))

        connection = smtplib.SMTP (self.smtp_server, self.smtp_port, timeout=10)
        connection.ehlo()
        if self.do_starttls:
            connection.starttls ()
        else:
            logging.error ("The e-mail interface hasn't been tested without STARTTLS.")
            logging.error ("Please review the code before continuing.")
            return False

        try:
            connection.login (self.smtp_username, self.smtp_password)
        except smtplib.SMTPAuthenticationError:
            logging.error ("Wrong credentials for authenticating to the e-mail server.")
            return False
        except (smtplib.SMTPHeloError,
                smtplib.SMTPNotSupportedError, smtplib.SMTPException) as error:
            logging.error ("Authenticating to the e-mail server failed: %s", error)
            return False

        try:
            connection.sendmail (self.from_address, to, message.as_string())
        except (smtplib.SMTPRecipientsRefused, smtplib.SMTPHeloError, smtplib.SMTPSenderRefused,
                smtplib.SMTPDataError, smtplib.SMTPNotSupportedError) as error:
            logging.error ("Sending e-mail failed: %s", error)
            return False

        connection.close()
        return True
