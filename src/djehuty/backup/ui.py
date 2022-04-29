"""This module contains the command-line interface for the 'backup' subcommand."""

import base64
import logging

from djehuty.backup import figshare
from djehuty.backup import database
from djehuty.utils.convenience import value_or

def main (figshare_token, figshare_stats_auth, account_id):
    """The main entry point for the 'backup' subcommand."""

    endpoint                = figshare.FigshareEndpoint()
    endpoint.token          = figshare_token
    endpoint.stats_auth     = base64.b64encode(figshare_stats_auth.encode('ascii')).decode('ascii')
    endpoint.institution_id = 898
    endpoint.rdf_store      = database.DatabaseInterface()
    accounts_written        = 0
    accounts_failed         = 0
    articles_written        = 0
    articles_failed         = 0
    collections_written     = 0
    collections_failed      = 0
    groups_written          = 0
    groups_failed           = 0

    accounts                = endpoint.get_institutional_accounts (account_id)
    number_of_accounts      = len(accounts)
    logging.info("Found %d institutional accounts.", number_of_accounts)
    for account_index, account in enumerate (accounts):
        logging.info("Processing %d of %d accounts.",
                     account_index + 1, number_of_accounts)
        if endpoint.rdf_store.insert_account (account):
            accounts_written += 1
        else:
            accounts_failed  += 1
            # When processing the account fails, don't attempt to
            # process collections and articles from this account.
            continue

        articles            = endpoint.get_articles_by_account (account["id"])
        number_of_articles  = len(articles)
        for article_index, article in enumerate (articles):
            logging.info ("Processing article %d of %d.",
                          article_index + 1, number_of_articles)
            if endpoint.rdf_store.insert_article (article):
                articles_written += 1
            else:
                articles_failed  += 1

            versions = value_or (article, "versions", [])
            for version in versions:
                if not endpoint.rdf_store.insert_article (version):
                    logging.error("Inserting a version of %s failed.", article['id'])

        del articles

        collections = endpoint.get_collections_by_account (account["id"])
        number_of_collections = len(collections)
        for collection_index, collection in enumerate (collections):
            logging.info ("Processing collection %d of %d.",
                          collection_index + 1, number_of_collections)
            if endpoint.rdf_store.insert_collection (collection, account["id"]):
                collections_written += 1
            else:
                collections_failed += 1

            versions = value_or (collection, "versions", [])
            for version in versions:
                if not endpoint.rdf_store.insert_collection (version, account["id"]):
                    logging.error("Inserting a version of %s failed.", collection['id'])

        del collections

    del accounts
    groups           = endpoint.get_institutional_groups()
    number_of_groups = len(groups)
    for group_index, group in enumerate (groups):
        logging.info ("Processing group %d of %d.", group_index + 1, number_of_groups)
        if endpoint.rdf_store.insert_institution_group (group):
            groups_written += 1
        else:
            groups_failed += 1

    del groups
    logging.info ("Serializing the RDF triplets...")
    endpoint.rdf_store.serialize ()

    if accounts_written > 0:
        logging.info("Succesfully processed %d accounts.", accounts_written)
    if articles_written > 0:
        logging.info("Succesfully processed %d articles.", articles_written)
    if collections_written > 0:
        logging.info("Succesfully processed %d collections.", collections_written)
    if groups_written > 0:
        logging.info("Succesfully processed %d groups.", groups_written)

    if accounts_failed > 0:
        logging.info("Failed to process %d accounts.", accounts_failed)
    if articles_failed > 0:
        logging.info("Failed to process %d articles.", articles_failed)
    if collections_failed > 0:
        logging.info("Failed to process %d collections.", collections_failed)
    if groups_failed > 0:
        logging.info("Failed to process %d groups.", groups_failed)

    return True
