"""
This module contains procedures to format a record from
djehuty.database to be backward-compatible with Figshare.
"""

from djehuty.utils import convenience as conv

def format_account_record (record):
    """Record formatter for accounts."""
    return {
        "id":             conv.value_or_none(record, "account_id"),
        "uuid":           conv.value_or_none(record, "uuid"),
        "first_name":     conv.value_or_none(record, "first_name"),
        "last_name":      conv.value_or_none(record, "last_name"),
        "is_active":      bool(conv.value_or_none(record, "active")),
        "is_public":      bool(conv.value_or_none(record, "public")),
        "job_title":      conv.value_or_none(record, "job_title"),
        "orcid_id":       conv.value_or (record, "orcid_id", ""),
    }

def format_dataset_record (record):
    """Record formatter for datasets."""

    if (bool(conv.value_or (record, "is_embargoed", False)) and
        conv.value_or (record, "embargo_type", "") == "article"):
        return {
            "embargo_date":   conv.value_or_none(record, "embargo_until_date"),
            "embargo_type":   conv.value_or_none(record, "embargo_type"),
            "embargo_title":  conv.value_or(record, "embargo_title", ""),
            "embargo_reason": conv.value_or(record, "embargo_reason", ""),
        }

    return {
        "id":                      conv.value_or_none(record, "dataset_id"),
        "uuid":                    conv.value_or_none(record, "container_uuid"),
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
        },
        "resource_title":          conv.value_or_none(record, "resource_title"),
        "resource_doi":            conv.value_or_none(record, "resource_doi")
    }

def format_author_record (record):
    """Record formatter for authors."""
    return {
      "id":        conv.value_or_none(record, "id"),
      "uuid":      conv.value_or_none(record, "uuid"),
      "full_name": conv.value_or_none(record, "full_name"),
      "is_active": bool(conv.value_or_none(record, "is_active")),
      "url_name":  conv.value_or_none(record, "url_name"),
      "orcid_id":  conv.value_or(record, "orcid_id", "")
    }

def format_author_details_record (record):
    """Detailed record formatter for authors."""
    return {
      "first_name":     conv.value_or_none(record, "first_name"),
      "full_name":      conv.value_or_none(record, "full_name"),
      "group_id":       conv.value_or_none(record, "group_id"),
      "id":             conv.value_or_none(record, "id"),
      "uuid":           conv.value_or_none(record, "uuid"),
      "institution_id": conv.value_or_none(record, "institution_id"),
      "is_active":      bool(conv.value_or_none(record, "is_active")),
      "is_public":      bool(conv.value_or_none(record, "is_public")),
      "job_title":      conv.value_or_none(record, "job_title"),
      "last_name":      conv.value_or_none(record, "last_name"),
      "orcid_id":       conv.value_or (record, "orcid_id", ""),
      "url_name":       conv.value_or_none(record, "url_name")
    }

def format_file_for_dataset_record (record):
    """Record formatter for files."""
    return {
      "id":           conv.value_or_none(record, "id"),
      "uuid":         conv.value_or_none(record, "uuid"),
      "name":         conv.value_or_none(record, "name"),
      "size":         conv.value_or_none(record, "size"),
      "is_link_only": bool(conv.value_or_none(record, "is_link_only")),
      "download_url": conv.value_or_none(record, "download_url"),
      "supplied_md5": conv.value_or_none(record, "supplied_md5"),
      "computed_md5": conv.value_or_none(record, "computed_md5")
    }

def format_file_details_record (record):
    """Detailed record formatter for files."""
    return {
      "status":        conv.value_or_none(record, "status"),
      "viewer_type":   conv.value_or_none(record, "viewer_type"),
      "preview_state": conv.value_or_none(record, "preview_state"),
      "upload_url":    conv.value_or_none(record, "upload_url"),
      "upload_token":  conv.value_or_none(record, "upload_token"),
      "uuid":          conv.value_or_none(record, "uuid"),
      "id":            conv.value_or_none(record, "id"),
      "name":          conv.value_or_none(record, "name"),
      "size":          conv.value_or_none(record, "size"),
      "is_link_only":  conv.value_or_none(record, "is_link_only"),
      "download_url":  conv.value_or_none(record, "download_url"),
      "supplied_md5":  conv.value_or_none(record, "supplied_md5"),
      "computed_md5":  conv.value_or_none(record, "computed_md5")
    }

def format_custom_field_record (record):
    """Record formatter for custom fields."""
    return {
      "name":         conv.value_or_none(record, "name"),
      "value":        conv.value_or_none(record, "value"),
    }

def format_category_record (record):
    """Record formatter for categories."""
    return {
        "id":          conv.value_or_none(record, "id"),
        "uuid":        conv.value_or_none(record, "uuid"),
        "title":       conv.value_or_none(record, "title"),
        "parent_id":   conv.value_or_none(record, "parent_id"),
        "parent_uuid": conv.value_or_none(record, "parent_uuid"),
        "path":        conv.value_or(record, "path", ""),
        "source_id":   conv.value_or_none(record, "source_id"),
        "taxonomy_id": conv.value_or_none(record, "taxonomy_id"),
    }

def format_tag_record (record):
    """Record formatter for tags."""
    return conv.value_or_none(record, "tag")

def format_reference_record (record):
    """Record formatter for references."""
    return conv.value_or_none(record, "url")

def format_license_record (record):
    """Record formatter for licenses."""
    return {
        "value":         conv.value_or_none(record, "id"),
        "name":          conv.value_or_none(record, "name"),
        "url":           conv.value_or_none(record, "url"),
        # Extension for Djehuty.
        "type":          conv.value_or_none(record, "type"),
    }

def format_dataset_details_record (dataset, authors, files, custom_fields,
                                   tags, categories, funding, references,
                                   is_private=False):
    """Detailed record formatter for datasets."""

    is_embargoed = bool(conv.value_or (dataset, "is_embargoed", False))
    if (is_embargoed and
        conv.value_or (dataset, "embargo_type", "") == "article" and
        not is_private):
        return {
            "embargo_date":      conv.value_or_none(dataset, "embargo_until_date"),
            "embargo_type":      conv.value_or_none(dataset, "embargo_type"),
            "embargo_title":     conv.value_or(dataset, "embargo_title", ""),
            "embargo_reason":    conv.value_or(dataset, "embargo_reason", ""),
        }

    embargo_until_date = conv.value_or_none(dataset, "embargo_until_date")
    embargo_allow_access_requests = conv.value_or (dataset, "embargo_allow_access_requests", False)
    embargo_option = None

    if (is_embargoed and
        embargo_allow_access_requests and
        embargo_until_date is None):
        embargo_option = { "id": 1000, "type": "restricted_access" }

    if (is_embargoed and
        not embargo_allow_access_requests and
        embargo_until_date is None):
        embargo_option = { "id": 1001, "type": "closed_access" }

    return {
        "files":             list (map (format_file_for_dataset_record, files)),
        "custom_fields":     list (map (format_custom_field_record, custom_fields)),
        "authors":           list (map (format_author_record, authors)),
        "figshare_url":      conv.value_or_none(dataset, "figshare_url"),
        "description":       conv.value_or_none(dataset, "description"),
        "funding":           conv.value_or_none(dataset, "funding"),
        "funding_list":      list (map (format_funding_record, funding)),
        "version":           conv.value_or_none(dataset, "version"),
        "status":            conv.value_or_none(dataset, "status"),
        "size":              conv.value_or_none(dataset, "size"),
        "created_date":      conv.value_or_none(dataset, "created_date"),
        "modified_date":     conv.value_or_none(dataset, "modified_date"),
        "is_public":         bool(conv.value_or_none(dataset, "is_public")),
        "is_confidential":   bool(conv.value_or_none(dataset, "is_confidential")),
        "is_metadata_record": bool(conv.value_or_none(dataset, "is_metadata_record")),
        "confidential_reason": conv.value_or(dataset, "confidential_reason", ""),
        "metadata_reason":   conv.value_or(dataset, "metadata_reason", ""),
        "license": {
            "value":         conv.value_or_none(dataset, "license_id"),
            "name":          conv.value_or_none(dataset, "license_name"),
            "url":           conv.value_or_none(dataset, "license_url"),
        },
        "tags":              list (map (format_tag_record, tags)),
        "categories":        list (map (format_category_record, categories)),
        "references":        list (map (format_reference_record, references)),
        "has_linked_file":   bool(conv.value_or_none(dataset, "has_linked_file")),
        "citation":          conv.value_or_none(dataset, "citation"),
#        "is_active":         conv.value_or_none(dataset, "is_active"),
        "is_embargoed":      bool(conv.value_or_none(dataset, "is_embargoed")),
        "embargo_date":      conv.value_or_none(dataset, "embargo_until_date"),
        "embargo_type":      conv.value_or_none(dataset, "embargo_type"),
        "embargo_title":     conv.value_or(dataset, "embargo_title", ""),
        "embargo_reason":    conv.value_or(dataset, "embargo_reason", ""),
        "embargo_options":   [embargo_option] if embargo_option is not None else [],
        "id":                conv.value_or_none(dataset, "dataset_id"),
        "title":             conv.value_or_none(dataset, "title"),
        "doi":               conv.value_or_none(dataset, "doi"),
        "handle":            conv.value_or(dataset, "handle", ""),
        "url":               conv.value_or_none(dataset, "url"),
        "published_date":    conv.value_or_none(dataset, "published_date"),
        "thumb":             conv.value_or(dataset, "thumb", ""),
        "defined_type":      conv.value_or_none(dataset, "defined_type"),
        "defined_type_name": conv.value_or_none(dataset, "defined_type_name"),
        "group_id":          conv.value_or_none(dataset, "group_id"),
        "url_private_api":   conv.value_or_none(dataset, "url_private_api"),
        "url_public_api":    conv.value_or_none(dataset, "url_public_api"),
        "url_private_html":  conv.value_or_none(dataset, "url_private_html"),
        "url_public_html":   conv.value_or_none(dataset, "url_public_html"),
        "timeline": {
            "posted":        conv.value_or_none(dataset, "timeline_posted"),
            "revision":      conv.value_or_none(dataset, "timeline_revision"),
            "submission":    conv.value_or_none(dataset, "timeline_submission"),
            "firstOnline":   conv.value_or_none(dataset, "timeline_first_online"),
            "publisherPublication": conv.value_or_none(dataset, "timeline_publisher_publication"),
        },
        "resource_title":    conv.value_or(dataset, "resource_title", ""),
        "resource_doi":      conv.value_or(dataset, "resource_doi", ""),
        "agreed_to_deposit_agreement": bool(conv.value_or_none (dataset, "agreed_to_deposit_agreement")),
        "agreed_to_publish": bool(conv.value_or_none(dataset, "agreed_to_publish"))
    }

def format_dataset_embargo_option_record (record):
    """Record formatter for embargo options."""
    return {
        "id":                conv.value_or_none (record, "id"),
        "type":              conv.value_or_none (record, "type"),
        "ip_name":           conv.value_or_none (record, "ip_name")
    }

def format_dataset_embargo_record (dataset):
    """Record formatter for embargos."""
    return {
        "is_embargoed":      bool(conv.value_or_none(dataset, "is_embargoed")),
        "embargo_date":      conv.value_or_none(dataset, "embargo_until"),
        "embargo_type":      conv.value_or(dataset, "embargo_type", "file"),
        "embargo_title":     conv.value_or(dataset, "embargo_title", ""),
        "embargo_reason":    conv.value_or(dataset, "embargo_reason", ""),

        # Embargo options are irrelevant outside of Figshare.
        "embargo_options":   [],
    }

def format_dataset_confidentiality_record (dataset):
    """Record formatter for confidentiality."""
    return {
        "is_confidential":   bool(conv.value_or_none(dataset, "is_confidential")),
        "reason": conv.value_or(dataset, "confidential_reason", ""),
    }

def format_dataset_version_record (record):
    """Record formatter for dataset versions."""
    return {
        "version":           conv.value_or_none(record, "version"),
        "url":               conv.value_or_none(record, "url")
    }

def format_collection_record (record):
    """Record formatter for collections."""
    return {
        "id":                conv.value_or_none(record, "collection_id"),
        "uuid":              conv.value_or_none(record, "container_uuid"),
        "title":             conv.value_or_none(record, "title"),
        "doi":               conv.value_or_none(record, "doi"),
        "handle":            conv.value_or(record, "handle", ""),
        "url":               conv.value_or_none(record, "url"),
        "timeline": {
            "posted":        conv.value_or_none(record, "timeline_posted"),
            "submission":    conv.value_or_none(record, "timeline_submission"),
            "revision":      conv.value_or_none(record, "timeline_revision"),
            "firstOnline":   conv.value_or_none(record, "timeline_first_online"),
            "publisherPublication": conv.value_or_none(record, "timeline_publisher_publication"),
        },
        "published_date":    conv.value_or_none(record, "published_date"),
    }

def format_collection_details_record (collection, funding, categories,
                                      references, tags, authors, custom_fields,
                                      datasets_count):
    """Detailed record formatter for collections."""
    return {
        "version":           conv.value_or_none(collection, "version"),
        "resource_id":       conv.value_or(collection, "resource_id", ""),
        "resource_doi":      conv.value_or(collection, "resource_doi", ""),
        "resource_title":    conv.value_or(collection, "resource_title", ""),
        "resource_link":     conv.value_or(collection, "resource_link", ""),
        "resource_version":  conv.value_or_none(collection, "resource_version"),
        "description":       conv.value_or_none(collection, "description"),
        "categories":        list (map (format_category_record, categories)),
        "references":        list (map (format_reference_record, references)),
        "tags":              list (map (format_tag_record, tags)),
        "authors":           list (map (format_author_record, authors)),
        "funding":           list (map (format_funding_record, funding)),
        "institution_id":    conv.value_or_none(collection, "institution_id"),
        "group_id":          conv.value_or_none(collection, "group_id"),
        "group_resource_id": conv.value_or_none(collection, "group_resource_id"),
        "articles_count":    0 if datasets_count is None else datasets_count,
        "public":            bool(conv.value_or_none(collection, "is_public")),
        "custom_fields":     list (map (format_custom_field_record, custom_fields)),
        "citation":          conv.value_or_none(collection, "citation"),
        "created_date":      conv.value_or_none(collection, "created_date"),
        "modified_date":     conv.value_or_none(collection, "modified_date"),
        "id":                conv.value_or_none(collection, "collection_id"),
        "uuid":              conv.value_or_none(collection, "container_uuid"),
        "title":             conv.value_or_none(collection, "title"),
        "doi":               conv.value_or_none(collection, "doi"),
        "handle":            conv.value_or(collection, "handle", ""),
        "url":               conv.value_or_none(collection, "url"),
        "published_date":    conv.value_or_none(collection, "published_date"),
        "timeline": {
            "posted":               conv.value_or_none(collection, "timeline_posted"),
            "firstOnline":          conv.value_or_none(collection, "timeline_first_online"),
            "revision":             conv.value_or_none(collection, "timeline_revision"),
            "submission":           conv.value_or_none(collection, "timeline_submission"),
            "publisherPublication": conv.value_or_none(collection, "timeline_publisher_publication")
        }
    }

def format_funding_record (record):
    """Record formatter for funding."""
    return {
        "id":                conv.value_or_none(record, "id"),
        "uuid":              conv.value_or_none(record, "uuid"),
        "title":             conv.value_or_none(record, "title"),
        "grant_code":        conv.value_or_none(record, "grant_code"),
        "funder_name":       conv.value_or_none(record, "funder_name"),
        "is_user_defined":   conv.value_or_none(record, "is_user_defined"),
        "url":               conv.value_or_none(record, "url")
    }

def format_version_record (record):
    """Record formatter for versions."""
    version = conv.value_or_none (record, "version")
    url     = conv.value_or_none (record, "url_public_api")

    return {
        "version": version,
        "url": f"{url}/versions/{version}"
    }

def format_private_links_record (record):
    """Record formatter for private links."""
    return {
        "id":           conv.value_or_none(record, "id_string"),
        "is_active":    bool(conv.value_or_none(record, "is_active")),
        "expires_date": conv.value_or_none(record, "expires_date")
    }

def format_group_record (record):
    """Record formatter for groups."""
    return {
      "id":            conv.value_or_none(record, "id"),
      "parent_id":     conv.value_or_none(record, "parent_id"),
      "name":          conv.value_or_none(record, "name"),
      "association":   conv.value_or_none(record, "association"),
    }
