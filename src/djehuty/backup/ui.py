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

def process_datasets_for_account (endpoint, account):
    """Processes the datasets for ACCOUNT."""

    datasets_written = 0
    datasets_failed  = 0

    account["uri"] = endpoint.rdf_store.insert_account (account)
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
        if endpoint.rdf_store.insert_dataset (dataset):
            datasets_written += 1
        else:
            datasets_failed  += 1

        versions = value_or (dataset, "versions", [])
        for version in versions:
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
        if endpoint.rdf_store.insert_collection (collection,
                                                 account["id"],
                                                 account["uri"]):
            collections_written += 1
        else:
            collections_failed += 1

        versions = value_or (collection, "versions", [])
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
    except KeyError:
        failed    += 1

    return { "written": written, "failed": failed }

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
    datasets_written        = 0
    datasets_failed         = 0
    collections_written     = 0
    collections_failed      = 0
    author_links_written    = 0
    author_links_failed     = 0
    groups_written          = 0
    groups_failed           = 0
    start_time              = time.perf_counter()

    accounts                = endpoint.get_institutional_accounts (account_id)
    number_of_accounts      = len(accounts)
    logging.info("Found %d institutional accounts.", number_of_accounts)
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
    if datasets_written > 0:
        logging.info("Succesfully processed %d datasets.", datasets_written)
    if collections_written > 0:
        logging.info("Succesfully processed %d collections.", collections_written)
    if groups_written > 0:
        logging.info("Succesfully processed %d groups.", groups_written)
    if author_links_written > 0:
        logging.info("Succesfully linked %d authors to accounts.", author_links_written)

    if accounts_failed > 0:
        logging.info("Failed to process %d accounts.", accounts_failed)
    if datasets_failed > 0:
        logging.info("Failed to process %d datasets.", datasets_failed)
    if collections_failed > 0:
        logging.info("Failed to process %d collections.", collections_failed)
    if groups_failed > 0:
        logging.info("Failed to process %d groups.", groups_failed)
    if author_links_failed > 0:
        logging.info("Failed to link %d authors to accounts.", author_links_failed)

    end_time      = time.perf_counter()
    logging.info ("This run took %.2f seconds", end_time - start_time)

    return True
