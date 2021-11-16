from rdbackup.utils import convenience

##
## This module contains procedures to format a record from
## rdbackup.database to be backward-compatible with Figshare.
##

def format_article_record (record):
    return {
        "id":                      convenience.value_or_none(record, "id"),
        "title":                   convenience.value_or_none(record, "title"),
        "doi":                     convenience.value_or_none(record, "doi"),
        "handle":                  convenience.value_or_none(record, "handle"),
        "url":                     convenience.value_or_none(record, "url"),
        "published_date":          convenience.value_or_none(record, "published_date"),
        "thumb":                   convenience.value_or_none(record, "thumb"),
        "defined_type":            convenience.value_or_none(record, "defined_type"),
        "defined_type_name":       convenience.value_or_none(record, "defined_type_name"),
        "group_id":                convenience.value_or_none(record, "group_id"),
        "url_private_api":         convenience.value_or_none(record, "url_private_api"),
        "url_public_api":          convenience.value_or_none(record, "url_public_api"),
        "url_private_html":        convenience.value_or_none(record, "url_private_html"),
        "url_public_html":         convenience.value_or_none(record, "url_public_html"),
        "timeline": {
            "posted":              convenience.value_or_none(record, "timeline_posted"),
            "firstOnline":         convenience.value_or_none(record, "timeline_first_online"),
            "revision":            convenience.value_or_none(record, "timeline_revision"),
            "publisherAcceptance": convenience.value_or_none(record, "timeline_publisher_acceptance"),
        },
        "resource_title":          convenience.value_or_none(record, "resource_title"),
        "resource_doi":            convenience.value_or_none(record, "resource_doi")
    }

def format_article_version_record (record):
    return [{
        "version": 1,
        "url": "https://api.figshare.com/v2/articles/17013092/versions/1"
    }, {
        "version": 2,
        "url": "https://api.figshare.com/v2/articles/17013092/versions/2"
    }]

def format_collection_record (record):
    return False
