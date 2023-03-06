"""
This module contains the command-line interface for the 'backup' subcommand.
"""

import base64
import gc
import logging
import time
import sys
import os

import concurrent.futures
from djehuty.backup import figshare
from djehuty.backup import database
from djehuty.utils.convenience import value_or

def process_datasets_for_account (endpoint, account):
    """Processes the datasets for ACCOUNT."""

    datasets_written = 0
    datasets_failed  = 0

    if not account["uri"]:
        # When processing the account fails, don't attempt to
        # process collections and datasets from this account.
        return False

    datasets            = endpoint.get_datasets_by_account (account["id"],
                                                            account["uri"])
    number_of_datasets  = len(datasets)
    for dataset_index, dataset in enumerate (datasets):
        logging.info ("Processing dataset %d of %d.",
                      dataset_index + 1, number_of_datasets)

        versions = value_or (dataset, "versions", [])

        # Only insert the draft dataset when it has changed since the last
        # publication, which we check by modified_date.
        try:
            if not (versions and versions[-1]["modified_date"] == dataset["modified_date"]):
                if endpoint.rdf_store.insert_dataset (dataset):
                    datasets_written += 1
                else:
                    datasets_failed  += 1
        except (KeyError, IndexError):
            pass

        for version in versions:
            version["account_uri"] = dataset["account_uri"]
            if not endpoint.rdf_store.insert_dataset (version):
                logging.error("Inserting a version of %s failed.", dataset['id'])

    del datasets
    return { "written": datasets_written, "failed": datasets_failed }

def process_collections_for_account (endpoint, account):
    """Processes the collections for ACCOUNT."""

    collections_written     = 0
    collections_failed      = 0
    collections             = endpoint.get_collections_by_account (account["id"],
                                                                   account["uri"])
    number_of_collections   = len(collections)
    for collection_index, collection in enumerate (collections):
        logging.info ("Processing collection %d of %d.",
                      collection_index + 1, number_of_collections)

        versions = value_or (collection, "versions", [])

        # Only insert the draft collection when it has changed since the last
        # publication, which we check by modified_date.
        try:
            if not (versions and versions[-1]["modified_date"] == collection["modified_date"]):
                if endpoint.rdf_store.insert_collection (collection,
                                                         account["id"],
                                                         account["uri"]):
                    collections_written += 1
                else:
                    collections_failed += 1
        except (KeyError, IndexError):
            pass

        for version in versions:
            if not endpoint.rdf_store.insert_collection (version,
                                                         account["id"],
                                                         account["uri"]):
                logging.error("Inserting a version of %s failed.", collection['id'])

    del collections
    return { "written": collections_written, "failed": collections_failed }

def process_author_links_for_account (endpoint, account):
    """Procedure to link authors to accounts."""

    written = 0
    failed  = 0

    try:
        author_id  = endpoint.get_author_for_account (account["id"])
        author_uri = endpoint.rdf_store.record_uri ("Author", "id", author_id)
        endpoint.rdf_store.insert_account_author_link (account["uri"], author_uri)
        written   += 1
    except (KeyError, AssertionError):
        failed    += 1

    return { "written": written, "failed": failed }

def show_if_relevant (score, suffix, prefix):
    """Emits a log message when SCORE > 0."""
    if score > 0:
        logging.info("%s processed %d %s.", prefix, score, suffix)

def main (figshare_token, figshare_stats_auth, account_id, api_url):
    """The main entry point for the 'backup' subcommand."""

    # Get rid of "Connection pool is full" messages.
    logging.getLogger("urllib3.connectionpool").setLevel(logging.ERROR)

    workers                 = min (os.cpu_count() * 4, 8)
    logging.info("Using a maximum of %d simultaneous connections.", workers)

    endpoint                = figshare.FigshareEndpoint(workers)
    endpoint.token          = figshare_token
    endpoint.stats_auth     = base64.b64encode(figshare_stats_auth.encode('ascii')).decode('ascii')
    endpoint.institution_id = 898
    endpoint.rdf_store      = database.DatabaseInterface()

    if api_url is not None:
        endpoint.base = api_url

    accounts_written        = 0
    accounts_failed         = 0
    datasets_written        = 0
    datasets_failed         = 0
    collections_written     = 0
    collections_failed      = 0
    author_links_written    = 0
    author_links_failed     = 0
    start_time              = time.perf_counter()

    if not endpoint.rdf_store.insert_static_triplets ():
        logging.error ("Failed to insert static triplets")

    accounts                = endpoint.get_institutional_accounts ()
    number_of_accounts      = len(accounts)
    logging.info("Inserting %d institutional accounts.", number_of_accounts)
    for account in accounts:
        account["uri"] = endpoint.rdf_store.insert_account (account)

    if account_id is not None:
        account_id = int(account_id)
        new_accounts = None
        for account in accounts:
            if account["id"] == account_id:
                new_accounts = [account]
                break
        if new_accounts is None:
            logging.error("Unable to find account %s", account_id)
            sys.exit (0)

        accounts = new_accounts
        logging.info("Limiting scope to account %d", account_id)

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as runner:
        results = [runner.submit(process_datasets_for_account, endpoint, account)
                   for account in accounts]
        for response in results:
            result = response.result()
            datasets_failed  += result["failed"]
            datasets_written += result["written"]

    gc.collect()

    ## We translate the dataset IDs associated to collections to their
    ## container URIs.  So we have to insert all datasets before we can
    ## translate the dataset IDs for the collections.
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as runner:
        results = [runner.submit(process_collections_for_account, endpoint, account)
                   for account in accounts]
        for response in results:
            result = response.result()
            collections_failed  += result["failed"]
            collections_written += result["written"]

    ## Gather links between accounts and authors.
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as runner:
        results = [runner.submit(process_author_links_for_account, endpoint, account)
                   for account in accounts]
        for response in results:
            result = response.result()
            author_links_failed  += result["failed"]
            author_links_written += result["written"]

    del accounts
    gc.collect()

    ## Serializing seems to take ~300 megabytes of memory.  Before doing
    ## so, it's a great moment to reduce the memory footprint by
    ## deallocating what we no longer need.
    del endpoint.author_ids
    del endpoint.rdf_store.container_uris
    gc.collect()

    logging.info ("Serializing the RDF triplets...")
    endpoint.rdf_store.serialize ()

    show_if_relevant (accounts_written,     "accounts",            "Succesfully")
    show_if_relevant (datasets_written,     "datasets",            "Succesfully")
    show_if_relevant (collections_written,  "collections",         "Succesfully")
    show_if_relevant (author_links_written, "authors to accounts", "Succesfully linked")

    show_if_relevant (accounts_failed,     "accounts",            "Failed")
    show_if_relevant (datasets_failed,     "datasets",            "Failed")
    show_if_relevant (collections_failed,  "collections",         "Failed")
    show_if_relevant (author_links_failed, "authors to accounts", "Failed to link")

    end_time      = time.perf_counter()
    logging.info ("This run took %.2f seconds", end_time - start_time)

    return True
