"""
This module contains procedures to format a record from
rdbackup.database to be backward-compatible with Figshare.
"""

from rdbackup.utils import convenience as conv

def format_article_record (record):
    return {
        "id":                      conv.value_or_none(record, "id"),
        "title":                   conv.value_or_none(record, "title"),
        "doi":                     conv.value_or_none(record, "doi"),
        "handle":                  conv.value_or_none(record, "handle"),
        "url":                     conv.value_or_none(record, "url"),
        "published_date":          conv.value_or_none(record, "published_date"),
        "thumb":                   conv.value_or_none(record, "thumb"),
        "defined_type":            conv.value_or_none(record, "defined_type"),
        "defined_type_name":       conv.value_or_none(record, "defined_type_name"),
        "group_id":                conv.value_or_none(record, "group_id"),
        "url_private_api":         conv.value_or_none(record, "url_private_api"),
        "url_public_api":          conv.value_or_none(record, "url_public_api"),
        "url_private_html":        conv.value_or_none(record, "url_private_html"),
        "url_public_html":         conv.value_or_none(record, "url_public_html"),
        "timeline": {
            "posted":              conv.value_or_none(record, "timeline_posted"),
            "firstOnline":         conv.value_or_none(record, "timeline_first_online"),
            "revision":            conv.value_or_none(record, "timeline_revision"),
            "publisherAcceptance": conv.value_or_none(record, "timeline_publisher_acceptance"),
        },
        "resource_title":          conv.value_or_none(record, "resource_title"),
        "resource_doi":            conv.value_or_none(record, "resource_doi")
    }

def format_author_record (record):
    return {
      "id":        conv.value_or_none(record, "id"),
      "full_name": conv.value_or_none(record, "full_name"),
      "is_active": conv.value_or_none(record, "is_active"),
      "url_name":  conv.value_or_none(record, "url_name"),
      "orcid_id":  conv.value_or_none(record, "orcid_id")
    }

def format_file_for_article_record (record):
    return {
      "id":           conv.value_or_none(record, "id"),
      "name":         conv.value_or_none(record, "name"),
      "size":         conv.value_or_none(record, "size"),
      "is_link_only": conv.value_or_none(record, "is_link_only"),
      "download_url": conv.value_or_none(record, "download_url"),
      "supplied_md5": conv.value_or_none(record, "supplied_md5"),
      "computed_md5": conv.value_or_none(record, "computed_md5")
    }

def format_file_details_record (record):
    return {
      "status":        conv.value_or_none(record, "status"),
      "viewer_type":   conv.value_or_none(record, "viewer_type"),
      "preview_state": conv.value_or_none(record, "preview_state"),
      "upload_url":    conv.value_or_none(record, "upload_url"),
      "upload_token":  conv.value_or_none(record, "upload_token"),
      "id":            conv.value_or_none(record, "id"),
      "name":          conv.value_or_none(record, "name"),
      "size":          conv.value_or_none(record, "size"),
      "is_link_only":  conv.value_or_none(record, "is_link_only"),
      "download_url":  conv.value_or_none(record, "download_url"),
      "supplied_md5":  conv.value_or_none(record, "supplied_md5"),
      "computed_md5":  conv.value_or_none(record, "computed_md5")
    }

def format_custom_field_record (record):
    return {
      "name":         conv.value_or_none(record, "name"),
      "value":        conv.value_or_none(record, "value"),
    }

def format_category_record (record):
    return {
        "parent_id":  conv.value_or_none(record, "parent_id"),
        "id":         conv.value_or_none(record, "id"),
        "title":      conv.value_or_none(record, "title")
    }

def format_tag_record (record):
    return conv.value_or_none(record, "tag")

def format_article_details_record (article, authors, files, custom_fields, tags, categories):
    return {
        "figshare_url":      conv.value_or_none(article, "figshare_url"),
        "resource_title":    conv.value_or_none(article, "resource_title"),
        "resource_doi":      conv.value_or_none(article, "resource_doi"),
        "files":             list (map (format_file_for_article_record, files)),
        "authors":           list (map (format_author_record, authors)),
        "custom_fields":     list (map (format_custom_field_record, custom_fields)),
        ## TODO: Currently not stored in the backup.
        #"embargo_options": [
        #    {
        #        "id": 364,
        #        "type": "ip_range",
        #        "ip_name": "Figshare IP range"
        #    }
        #],
        "citation":          conv.value_or_none(article, "citation"),
        "confidential_reason": conv.value_or_none(article, "confidential_reason"),
        "embargo_type":      conv.value_or_none(article, "embargo_type"),
        "is_confidential":   conv.value_or_none(article, "is_confidential"),
        "size":              conv.value_or_none(article, "size"),
        "funding":           conv.value_or_none(article, "funding"),
        ## TODO: Currently not stored in the backup.
        #"funding_list": [
        #    0
        #],
        "tags":              list (map (format_tag_record, tags)),
        "version":           conv.value_or_none(article, "version"),
        "is_active":         conv.value_or_none(article, "is_active"),
        "is_metadata_record": conv.value_or_none(article, "is_metadata_record"),
        "metadata_reason":   conv.value_or_none(article, "metadata_reason"),
        "status":            conv.value_or_none(article, "status"),
        "description":       conv.value_or_none(article, "description"),
        "is_embargoed":      conv.value_or_none(article, "is_embargoed"),
        "embargo_date":      conv.value_or_none(article, "embargo_date"),
        "is_public":         conv.value_or_none(article, "is_public"),
        "modified_date":     conv.value_or_none(article, "modified_date"),
        "created_date":      conv.value_or_none(article, "created_date"),
        "has_linked_file":   conv.value_or_none(article, "has_linked_file"),
        "categories":        list (map (format_category_record, categories)),
        "license": {
            "value":         conv.value_or_none(article, "license_id"),
            "name":          conv.value_or_none(article, "license_name"),
            "url":           conv.value_or_none(article, "license_url"),
        },
        "embargo_title":     conv.value_or_none(article, "embargo_title"),
        "embargo_reason":    conv.value_or_none(article, "embargo_reason"),
        "references": [
            "http://figshare.com",
            "http://figshare.com/api"
        ],
        "id":                conv.value_or_none(article, "id"),
        "title":             conv.value_or_none(article, "title"),
        "doi":               conv.value_or_none(article, "doi"),
        "handle":            conv.value_or_none(article, "handle"),
        "group_id":          conv.value_or_none(article, "group_id"),
        "url":               conv.value_or_none(article, "url"),
        "url_public_html":   conv.value_or_none(article, "url_public_html"),
        "url_public_api":    conv.value_or_none(article, "url_public_api"),
        "url_private_html":  conv.value_or_none(article, "url_private_html"),
        "url_private_api":   conv.value_or_none(article, "url_private_api"),
        "published_date":    conv.value_or_none(article, "published_date"),
        "timeline": {
            "posted":        conv.value_or_none(article, "timeline_posted"),
            "submission":    conv.value_or_none(article, "timeline_submission"),
            "revision":      conv.value_or_none(article, "timeline_revision"),
            "firstOnline":   conv.value_or_none(article, "timeline_first_online"),
            "publisherPublication": conv.value_or_none(article, "timeline_publisher_publication"),
            "publisherAcceptance": conv.value_or_none(article, "timeline_publisher_acceptance"),
        },
        "thumb":             conv.value_or_none(article, "thumb"),
        "defined_type":      conv.value_or_none(article, "defined_type"),
        "defined_type_name": conv.value_or_none(article, "defined_type_name"),
    }

def format_article_version_record (record):
    return {
        "version":           conv.value_or_none(record, "version"),
        "url":               conv.value_or_none(record, "url")
    }

def format_collection_record (record):
    return {
        "id":                conv.value_or_none(record, "id"),
        "title":             conv.value_or_none(record, "title"),
        "doi":               conv.value_or_none(record, "doi"),
        "handle":            conv.value_or_none(record, "handle"),
        "url":               conv.value_or_none(record, "url"),
        "timeline": {
            "posted":        conv.value_or_none(record, "timeline_posted"),
            "submission":    conv.value_or_none(record, "timeline_submission"),
            "revision":      conv.value_or_none(record, "timeline_revision"),
            "firstOnline":   conv.value_or_none(record, "timeline_first_online"),
            "publisherPublication": conv.value_or_none(record, "timeline_publisher_publication"),
            "publisherAcceptance": conv.value_or_none(record, "timeline_publisher_acceptance"),
        },
        "published_date":    conv.value_or_none(record, "published_date"),
    }

def format_collection_details_record (collection, funding, categories,
                                      references, tags, authors, custom_fields):
    return {
        "funding":           list (map (format_funding_record, funding)),
        "resource_id":       conv.value_or_none(collection, "resource_id"),
        "resource_doi":      conv.value_or_none(collection, "resource_doi"),
        "resource_title":    conv.value_or_none(collection, "resource_title"),
        "resource_link":     conv.value_or_none(collection, "resource_link"),
        "resource_version":  conv.value_or_none(collection, "resource_version"),
        "version":           conv.value_or_none(collection, "version"),
        "description":       conv.value_or_none(collection, "description"),
        "categories":        list (map (format_category_record, categories)),
        "references":        references,
        "tags":              list (map (format_tag_record, tags)),
        "authors":           list (map (format_author_record, authors)),
        "institution_id":    conv.value_or_none(collection, "institution_id"),
        "group_id":          conv.value_or_none(collection, "group_id"),
        "articles_count":    conv.value_or_none(collection, "articles_count"),
        "public":            conv.value_or_none(collection, "is_public"),
        "citation":          conv.value_or_none(collection, "citation"),
        "group_resource_id": conv.value_or_none(collection, "group_resource_id"),
        "custom_fields":     list (map (format_custom_field_record, custom_fields)),
        "modified_date":     conv.value_or_none(collection, "modified_date"),
        "created_date":      conv.value_or_none(collection, "created_date"),
        "timeline": {
            "posted":               conv.value_or_none(collection, "timeline_posted"),
            "firstOnline":          conv.value_or_none(collection, "timeline_first_online"),
            "revision":             conv.value_or_none(collection, "timeline_revision"),
            "publisherAcceptance":  conv.value_or_none(collection, "timeline_publisher_acceptance"),
            "submission":           conv.value_or_none(collection, "timeline_submission"),
            "publisherPublication": conv.value_or_none(collection, "timeline_publisher_publication")
        },
        "id":                conv.value_or_none(collection, "id"),
        "title":             conv.value_or_none(collection, "title"),
        "doi":               conv.value_or_none(collection, "doi"),
        "handle":            conv.value_or_none(collection, "handle"),
        "url":               conv.value_or_none(collection, "url"),
        "published_date":    conv.value_or_none(collection, "published_date")
    }

def format_funding_record (record):
    return {
        "id":                conv.value_or_none(record, "id"),
        "title":             conv.value_or_none(record, "title"),
        "grant_code":        conv.value_or_none(record, "grant_code"),
        "funder_name":       conv.value_or_none(record, "funder_name"),
        "is_user_defined":   conv.value_or_none(record, "is_user_defined"),
        "url":               conv.value_or_none(record, "url")
    }
