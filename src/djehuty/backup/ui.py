"""This module contains the command-line interface for the 'backup' subcommand."""

import base64
import logging

from djehuty.backup import figshare
from djehuty.backup import database
from djehuty.utils import convenience as conv

def main (figshare_token, figshare_stats_auth, db_host, db_username, db_password, db_name,
          since="1970-01-01"):
    """The main entry point for the 'backup' subcommand."""

    endpoint                = figshare.FigshareEndpoint()
    endpoint.token          = figshare_token
    endpoint.stats_auth     = base64.b64encode(figshare_stats_auth.encode('ascii')).decode('ascii')
    endpoint.institution_id = 898

    db = database.DatabaseInterface()
    connected = db.connect(db_host, db_username, db_password, db_name)

    if not connected:
        logging.error("Cannot establish a connection to the MySQL server.")
        return False

    accounts = endpoint.get_institutional_accounts ()
    logging.info("Found %d institutional accounts.", len(accounts))
    articles_written    = 0
    articles_failed     = 0
    collections_written = 0
    collections_failed  = 0
    for account in accounts:
        db.insert_account (account)

        articles = endpoint.get_articles_by_account (account["id"])
        for article in articles:
            if db.insert_article (article):
                articles_written += 1
            else:
                articles_failed  += 1

            versions = conv.value_or (article, "versions", [])
            for version in versions:
                if not db.insert_article (version):
                    logging.error("Inserting a version of {article['id']} failed.")

        collections = endpoint.get_collections_by_account (account["id"])
        for collection in collections:
            if db.insert_collection (collection, account["id"]):
                collections_written += 1
            else:
                collections_failed += 1

            versions = conv.value_or (collection, "versions", [])
            for version in versions:
                if not db.insert_collection (version, account["id"]):
                    logging.error("Inserting a version of {collection['id']} failed.")

    logging.info("Succesfully processed %d articles.", articles_written)
    logging.info("Failed to process %d articles.", articles_failed)
    logging.info("Succesfully processed %d collections.", collections_written)
    logging.info("Failed to process %d collections.", collections_failed)
    return True
