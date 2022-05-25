"""
This module contains the command-line interface for the 'backup' subcommand.
"""

import base64
import gc
import logging
import time
import os

import concurrent.futures
from djehuty.backup import figshare
from djehuty.backup import database
from djehuty.utils.convenience import value_or

def process_articles_for_account (endpoint, account):
    """Processes the datasets for ACCOUNT."""

    articles_written = 0
    articles_failed  = 0

    if not endpoint.rdf_store.insert_account (account):
        # When processing the account fails, don't attempt to
        # process collections and articles from this account.
        return False

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
    return { "written": articles_written, "failed": articles_failed }

def process_collections_for_account (endpoint, account):
    """Processes the collections for ACCOUNT."""

    collections_written     = 0
    collections_failed      = 0
    collections             = endpoint.get_collections_by_account (account["id"])
    number_of_collections   = len(collections)
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
    return { "written": collections_written, "failed": collections_failed }

def main (figshare_token, figshare_stats_auth, account_id):
    """The main entry point for the 'backup' subcommand."""

    workers                 = os.cpu_count() * 4
    logging.info("Using a maximum of %d simultaneous connections.", workers)

    endpoint                = figshare.FigshareEndpoint(workers)
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
    start_time              = time.perf_counter()

    accounts                = endpoint.get_institutional_accounts (account_id)
    number_of_accounts      = len(accounts)
    logging.info("Found %d institutional accounts.", number_of_accounts)
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as runner:
        results = [runner.submit(process_articles_for_account, endpoint, account)
                   for account in accounts]
        for response in results:
            result = response.result()
            articles_failed  += result["failed"]
            articles_written += result["written"]

    gc.collect()

    ## We translate the article IDs associated to collections to their
    ## container URIs.  So we have to insert all articles before we can
    ## translate the article IDs for the collections.
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as runner:
        results = [runner.submit(process_collections_for_account, endpoint, account)
                   for account in accounts]
        for response in results:
            result = response.result()
            collections_failed  += result["failed"]
            collections_written += result["written"]

    del accounts
    gc.collect()

    groups           = endpoint.get_institutional_groups()
    number_of_groups = len(groups)
    for group_index, group in enumerate (groups):
        logging.info ("Processing group %d of %d.", group_index + 1, number_of_groups)
        if endpoint.rdf_store.insert_institution_group (group):
            groups_written += 1
        else:
            groups_failed += 1

    del groups

    if not endpoint.rdf_store.insert_root_categories ():
        logging.error ("Failed to insert root categories")

    if not endpoint.rdf_store.insert_static_triplets ():
        logging.error ("Failed to insert static triplets")

    ## Serializing seems to take ~300 megabytes of memory.  Before doing
    ## so, it's a great moment to reduce the memory footprint by
    ## deallocating what we no longer need.
    del endpoint.author_ids
    del endpoint.rdf_store.container_uris
    gc.collect()

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

    end_time      = time.perf_counter()
    logging.info ("This run took %.2f seconds", end_time - start_time)

    return True
