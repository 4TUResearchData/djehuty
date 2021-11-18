from rdbackup.backup import figshare
from rdbackup.backup import database

import logging

def main (figshare_token, figshare_stats_auth, db_host, db_username, db_password, db_name,
          since="1970-01-01"):
    endpoint                = figshare.FigshareEndpoint()
    endpoint.token          = figshare_token
    endpoint.stats_auth     = base64.b64encode(fishare_stats_auth.encode('ascii')).decode('ascii')
    endpoint.institution_id = 898

    db = database.DatabaseInterface()
    connected = db.connect(db_host, db_username, db_password, db_name)

    if not connected:
        logging.error("Cannot establish a connection to the MySQL server.")
        return False

    accounts = endpoint.getInstitutionalAccounts()
    logging.info(f"Found {len(accounts)} institutional accounts.")
    articles_written    = 0
    articles_failed     = 0
    collections_written = 0
    collections_failed  = 0
    for account in accounts:
        db.insertAccount(account)

        articles = endpoint.getArticlesByAccount(account["id"])
        for article in articles:
            if db.insertArticle(article):
                articles_written += 1
            else:
                articles_failed  += 1

        collections = endpoint.getCollectionsByAccount(account["id"])
        for collection in collections:
            if db.insertCollection(collection):
                collections_written += 1
            else:
                collections_failed += 1

    logging.info(f"Succesfully processed {articles_written} articles.")
    logging.info(f"Failed to process {articles_failed} articles.")
    logging.info(f"Succesfully processed {collections_written} collections.")
    logging.info(f"Failed to process {collections_failed} collections.")
    return True
