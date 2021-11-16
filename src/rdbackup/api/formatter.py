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

def format_author_for_article_record (record):
    return {
      "id":        convenience.value_or_none(record, "id"),
      "full_name": convenience.value_or_none(record, "full_name"),
      "is_active": convenience.value_or_none(record, "is_active"),
      "url_name":  convenience.value_or_none(record, "url_name"),
      "orcid_id":  convenience.value_or_none(record, "orcid_id")
    }

def format_file_for_article_record (record):
    return {
      "id":           convenience.value_or_none(record, "id"),
      "name":         convenience.value_or_none(record, "name"),
      "size":         convenience.value_or_none(record, "size"),
      "is_link_only": convenience.value_or_none(record, "is_link_only"),
      "download_url": convenience.value_or_none(record, "download_url"),
      "supplied_md5": convenience.value_or_none(record, "supplied_md5"),
      "computed_md5": convenience.value_or_none(record, "computed_md5")
    }

def format_custom_field_for_article_record (record):
    return {
      "name":         convenience.value_or_none(record, "name"),
      "value":        convenience.value_or_none(record, "value"),
    }

def format_category_for_article_record (record):
    return {
        "parent_id":  convenience.value_or_none(record, "parent_id"),
        "id":         convenience.value_or_none(record, "id"),
        "title":      convenience.value_or_none(record, "title")
    }

def format_tag_for_article_record (record):
    return convenience.value_or_none(record, "tag")

def format_article_details_record (article, authors, files, custom_fields, tags, categories):
    return {
        "figshare_url":      convenience.value_or_none(article, "figshare_url"),
        "resource_title":    convenience.value_or_none(article, "resource_title"),
        "resource_doi":      convenience.value_or_none(article, "resource_doi"),
        "files":             list (map (format_file_for_article_record, files)),
        "authors":           list (map (format_author_for_article_record, authors)),
        "custom_fields":     list (map (format_custom_field_for_article_record, custom_fields)),
        ## TODO: Currently not stored in the backup.
        #"embargo_options": [
        #    {
        #        "id": 364,
        #        "type": "ip_range",
        #        "ip_name": "Figshare IP range"
        #    }
        #],
        "citation":          convenience.value_or_none(article, "citation"),
        "confidential_reason": convenience.value_or_none(article, "confidential_reason"),
        "embargo_type":      convenience.value_or_none(article, "embargo_type"),
        "is_confidential":   convenience.value_or_none(article, "is_confidential"),
        "size":              convenience.value_or_none(article, "size"),
        "funding":           convenience.value_or_none(article, "funding"),
        ## TODO: Currently not stored in the backup.
        #"funding_list": [
        #    0
        #],
        "tags":              list (map (format_tag_for_article_record, tags)),
        "version":           convenience.value_or_none(article, "version"),
        "is_active":         convenience.value_or_none(article, "is_active"),
        "is_metadata_record": convenience.value_or_none(article, "is_metadata_record"),
        "metadata_reason":   convenience.value_or_none(article, "metadata_reason"),
        "status":            convenience.value_or_none(article, "status"),
        "description":       convenience.value_or_none(article, "description"),
        "is_embargoed":      convenience.value_or_none(article, "is_embargoed"),
        "embargo_date":      convenience.value_or_none(article, "embargo_date"),
        "is_public":         convenience.value_or_none(article, "is_public"),
        "modified_date":     convenience.value_or_none(article, "modified_date"),
        "created_date":      convenience.value_or_none(article, "created_date"),
        "has_linked_file":   convenience.value_or_none(article, "has_linked_file"),
        "categories":        list (map (format_category_for_article_record, categories)),
        "license": {
            "value":         convenience.value_or_none(article, "license_id"),
            "name":          convenience.value_or_none(article, "license_name"),
            "url":           convenience.value_or_none(article, "license_url"),
        },
        "embargo_title":     convenience.value_or_none(article, "embargo_title"),
        "embargo_reason":    convenience.value_or_none(article, "embargo_reason"),
        "references": [
            "http://figshare.com",
            "http://figshare.com/api"
        ],
        "id":                convenience.value_or_none(article, "id"),
        "title":             convenience.value_or_none(article, "title"),
        "doi":               convenience.value_or_none(article, "doi"),
        "handle":            convenience.value_or_none(article, "handle"),
        "group_id":          convenience.value_or_none(article, "group_id"),
        "url":               convenience.value_or_none(article, "url"),
        "url_public_html":   convenience.value_or_none(article, "url_public_html"),
        "url_public_api":    convenience.value_or_none(article, "url_public_api"),
        "url_private_html":  convenience.value_or_none(article, "url_private_html"),
        "url_private_api":   convenience.value_or_none(article, "url_private_api"),
        "published_date":    convenience.value_or_none(article, "published_date"),
        "timeline": {
            "posted":        convenience.value_or_none(article, "timeline_posted"),
            "submission":    convenience.value_or_none(article, "timeline_submission"),
            "revision":      convenience.value_or_none(article, "timeline_revision"),
            "firstOnline":   convenience.value_or_none(article, "timeline_first_online"),
            "publisherPublication": convenience.value_or_none(article, "timeline_publisher_publication"),
            "publisherAcceptance": convenience.value_or_none(article, "timeline_publisher_acceptance"),
        },
        "thumb":             convenience.value_or_none(article, "thumb"),
        "defined_type":      convenience.value_or_none(article, "defined_type"),
        "defined_type_name": convenience.value_or_none(article, "defined_type_name"),
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
