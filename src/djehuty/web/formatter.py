"""
This module contains procedures to format a record from
djehuty.database to be backward-compatible with Figshare.
"""

from djehuty.utils import convenience as conv

def format_collaborator_record (record):
    """Record formatter for collaborators"""
    return {
        "uuid":           conv.value_or_none(record, "uuid"),
        "account_uuid":   conv.value_or_none (record, "account_uuid"),
        "first_name":     conv.value_or_none (record, "first_name"),
        "last_name":      conv.value_or_none(record, "last_name"),
        "email":          conv.value_or_none(record, "email"),
        "metadata_read":  conv.value_or_none (record, "metadata_read"),
        "metadata_edit":  conv.value_or_none(record, "metadata_edit"),
        "data_read":      conv.value_or_none(record, "data_read"),
        "data_edit":      conv.value_or_none(record, "data_edit"),
        "data_remove":    conv.value_or_none(record, "data_remove"),
        "is_supervisor":  conv.value_or_none (record, "is_supervisor"),
        "group_id":       conv.value_or_none (record, "group_id"),
        "group_name":     conv.value_or_none (record, "group_name"),
        "is_inferred":    conv.value_or(record, "is_inferred", False)
    }

def format_account_record (record):
    """Record formatter for accounts."""
    return {
        "id":             conv.value_or_none(record, "account_id"),
        "uuid":           conv.value_or_none(record, "uuid"),
        "first_name":     conv.value_or_none(record, "first_name"),
        "last_name":      conv.value_or_none(record, "last_name"),
        "full_name":      conv.value_or_none(record, "full_name"),
        "is_active":      bool(conv.value_or_none(record, "active")),
        "is_public":      bool(conv.value_or_none(record, "public")),
        "job_title":      conv.value_or_none(record, "job_title"),
        "orcid_id":       conv.value_or (record, "orcid_id", ""),
    }

def format_account_details_record (record):
    """Record formatter for accounts."""
    return {
        "id":             conv.value_or_none(record, "account_id"),
        "uuid":           conv.value_or_none(record, "uuid"),
        "first_name":     conv.value_or_none(record, "first_name"),
        "last_name":      conv.value_or_none(record, "last_name"),
        "full_name":      conv.value_or_none(record, "full_name"),
        "email":          conv.value_or_none(record, "email"),
        "is_active":      bool(conv.value_or_none(record, "active")),
        "is_public":      bool(conv.value_or_none(record, "public")),
        "job_title":      conv.value_or_none(record, "job_title"),
        "orcid_id":       conv.value_or (record, "orcid_id", ""),
    }

def collection_urls (record):
    """Returns generated variants of public-facing collection URLs when possible."""
    if "base_url" in record:
        version = ""
        if "version" in record:
            version = f"/{record['version']}"

        return {
            "url":              f"{record['base_url']}/v2/collections/{record['container_uuid']}",
            "url_private_api":  f"{record['base_url']}/v2/account/collections/{record['container_uuid']}",
            "url_public_api":   f"{record['base_url']}/v2/collections/{record['container_uuid']}",
            "url_private_html": f"{record['base_url']}/my/collections/{record['container_uuid']}/edit",
            "url_public_html":  f"{record['base_url']}/collections/{record['container_uuid']}{version}"
        }

    return {
        "url":              conv.value_or_none(record, "url"),
        "url_private_api":  conv.value_or_none(record, "url_private_api"),
        "url_public_api":   conv.value_or_none(record, "url_public_api"),
        "url_private_html": conv.value_or_none(record, "url_private_html"),
        "url_public_html":  conv.value_or_none(record, "url_public_html")
    }

def dataset_urls (record):
    """Returns generated variants of public-facing dataset URLs when possible."""

    if "base_url" in record:
        version = ""
        if "version" in record:
            version = f"/{record['version']}"
        return {
            "url":              f"{record['base_url']}/v2/articles/{record['container_uuid']}",
            "url_private_api":  f"{record['base_url']}/v2/account/articles/{record['container_uuid']}",
            "url_public_api":   f"{record['base_url']}/v2/articles/{record['container_uuid']}",
            "url_private_html": f"{record['base_url']}/my/datasets/{record['container_uuid']}/edit",
            "url_public_html":  f"{record['base_url']}/datasets/{record['container_uuid']}{version}"
        }

    return {
        "url":              conv.value_or_none(record, "url"),
        "url_private_api":  conv.value_or_none(record, "url_private_api"),
        "url_public_api":   conv.value_or_none(record, "url_public_api"),
        "url_private_html": conv.value_or_none(record, "url_private_html"),
        "url_public_html":  conv.value_or_none(record, "url_public_html")
    }

def format_codemeta_author_record (record, base_url):
    """Record formatter for an author as used in CodeMeta."""
    author = {
        "@type": "Person",
        "givenName": conv.value_or_none (record, "first_name"),
        "familyName": conv.value_or_none (record, "last_name"),
        "name": conv.value_or_none (record, "full_name"),
        "email": None,
    }

    orcid = conv.value_or_none (record, "orcid_id")
    if orcid is not None:
        author["@id"] = f"https://orcid.org/{orcid}"
    else:
        author["@id"] = f"{base_url}/authors/{record['uuid']}"

    return author

def format_codemeta_record (record, git_url, tags, authors, has_files, base_url):
    """Record formatter for the CodeMeta format."""

    title = conv.value_or_none (record, "git_repository_name")
    if title is None or title == "":
        title = conv.value_or_none (record, "title")

    if bool(conv.value_or (record, "is_embargoed", False)):
        return {
            "@context": "https://doi.org/10.5063/schema/codemeta-2.0",
            "@type": "SoftwareSourceCode",
            "name": title,
            "dateCreated": conv.value_or_none(record, "created_date"),
            "datePublished": conv.value_or_none(record, "published_date"),
            "embargoDate": conv.value_or_none(record, "embargo_until_date")
        }

    # Strip the HTML tags from the description.
    description = conv.value_or_none (record, "description")
    if description:
        description = conv.html_to_plaintext (description, True)

    output = {
        "@context": "https://doi.org/10.5063/schema/codemeta-2.0",
        "@type": "SoftwareSourceCode",
        "name": title,
        "license": conv.value_or_none (record, "license_spdx"),
        "dateCreated": conv.value_or_none(record, "created_date"),
        "datePublished": conv.value_or_none(record, "published_date"),
        "dateModified": conv.value_or_none(record, "modified_date"),
        "identifier": conv.value_or_none(record, "doi"),
        "description": [conv.value_or (record, "title", ""), description],
        "keywords": list (map (format_tag_record, tags)),
        "author": list (map (lambda author: format_codemeta_author_record (author, base_url), authors))
    }

    resource_doi = conv.value_or_none (record, "resource_doi")
    if resource_doi is not None:
        output["referencePublication"] = [{
            "@type": "ScholarlyArticle",
            "url": f"https://doi.org/{resource_doi}",
            "name": conv.value_or_none (record, "resource_title"),
            "@id": resource_doi
        }]
    else:
        output["referencePublication"] = []

    download_url = []
    if has_files and "version" in record and "container_uuid" in record:
        download_url = [f"{base_url}/ndownloader/items/{record['container_uuid']}/versions/{record['version']}"]

    if git_url:
        download_url.append (f"{git_url}/zip")
        output["codeRepository"] = git_url

    if download_url:
        output["downloadUrl"] = download_url

    if "version" in record:
        output["version"] = record["version"]

    return output

def format_rocrate_file_record (record):
    """Record formatter for RO-Crate file objects."""

    return {
        "@id": record["uuid"],
        "@type": "File",
        "name": conv.value_or_none (record, "name"),
        "contentSize": f"{conv.value_or_none(record, 'size')}",
        "contentUrl": file_download_url (record)
    }

def format_rocrate_record (base_url, site_name, record, ror_url, tags,
                           authors, files, git_url=None):
    """Record formatter for the RO-Crate format."""

    # Strip the HTML tags from the description.
    description = conv.value_or_none (record, "description")
    if description:
        description = conv.html_to_plaintext (description, True)

    ro_file_ids = []
    for file in files:
        file["base_url"] = base_url
        ro_file_ids.append({ "@id": file["uuid"] })

    is_embargoed = bool(conv.value_or (record, "is_embargoed", False))
    is_restricted = bool(conv.value_or (record, "is_restricted", False))
    if is_embargoed or is_restricted:
        file_records = []
    else:
        file_records = list (map (format_rocrate_file_record, files))

    publisher_records = []
    git_record = []
    ro_crate_meta_record = {
        "@id": "ro-crate-metadata.json",
        "@type": "CreativeWork",
        "conformsTo": { "@id": "https://w3id.org/ro/crate/1.1" },
        "about": { "@id": "./" }
    }
    dataset_record = {
        "@id": "./",
        "@type": "Dataset",
        "identifier": f"https://doi.org/{record['doi']}",
        "datePublished": conv.value_or_none(record, "published_date"),
        "name": conv.value_or_none (record, "title"),
        "description": description,
        "keywords": list (map (format_tag_record, tags)),
        "license": { "@id": conv.value_or_none (record, "license_spdx") },
        "author": list (map (lambda author: format_codemeta_author_record (author, base_url), authors)),
        "hasPart": list (map (lambda item: { "@id": item["@id"] }, file_records))
    }

    if git_url:
        title = conv.value_or_none (record, "git_repository_name")
        if title is None or title == "":
            title = conv.value_or_none (record, "title")

        git_record = [{
            "@id": record["git_uuid"],
            "@type": "SoftwareSourceCode",
            "name": title,
            "codeRepository": git_url,
        }]
        dataset_record["hasPart"].append({ "@id": record["git_uuid"] })

    if ror_url:
        publisher_records = [{
            "@id": ror_url,
            "@type": "Organization",
            "name": site_name,
            "url": base_url
        }]
        dataset_record["publisher"] = { "@id": ror_url }

    return {
        "@context": "https://w3id.org/ro/crate/1.1/context",
        "@graph": [ro_crate_meta_record, dataset_record] + git_record + publisher_records + file_records
    }

def format_dataset_record (record):
    """Record formatter for datasets."""

    urls = dataset_urls (record)
    if (bool(conv.value_or (record, "is_embargoed", False)) and
        conv.value_or (record, "embargo_type", "") == "article"):
        return {
            "uuid":           conv.value_or_none(record, "container_uuid"),
            "title":          conv.value_or_none(record, "title"),
            "embargo_date":   conv.value_or_none(record, "embargo_until_date"),
            "embargo_type":   conv.value_or_none(record, "embargo_type"),
            "embargo_title":  conv.value_or(record, "embargo_title", ""),
            "embargo_reason": conv.value_or(record, "embargo_reason", ""),
            "published_date": conv.value_or_none(record, "published_date"),
            "url_public_html": conv.value_or_none(urls, "url_public_html"),
            "timeline": {
                "posted":     conv.value_or_none(record, "timeline_posted"),
                "firstOnline": conv.value_or_none(record, "timeline_first_online"),
                "revision":   conv.value_or_none(record, "timeline_revision"),
            }
        }

    output = {
        "id":                      conv.value_or_none(record, "dataset_id"),
        "uuid":                    conv.value_or_none(record, "container_uuid"),
        "title":                   conv.value_or_none(record, "title"),
        "doi":                     conv.value_or_none(record, "doi"),
        "handle":                  conv.value_or_none(record, "handle"),
        "url":                     conv.value_or_none(urls, "url"),
        "published_date":          conv.value_or_none(record, "published_date"),
        "thumb":                   conv.value_or_none(record, "thumb"),
        "defined_type":            conv.value_or_none(record, "defined_type"),
        "defined_type_name":       conv.value_or_none(record, "defined_type_name"),
        "group_id":                conv.value_or_none(record, "group_id"),
        "url_private_api":         conv.value_or_none(urls, "url_private_api"),
        "url_public_api":          conv.value_or_none(urls, "url_public_api"),
        "url_private_html":        conv.value_or_none(urls, "url_private_html"),
        "url_public_html":         conv.value_or_none(urls, "url_public_html"),
        "timeline": {
            "posted":              conv.value_or_none(record, "timeline_posted"),
            "firstOnline":         conv.value_or_none(record, "timeline_first_online"),
            "revision":            conv.value_or_none(record, "timeline_revision"),
        },
        "resource_title":          conv.value_or_none(record, "resource_title"),
        "resource_doi":            conv.value_or_none(record, "resource_doi")
    }

    if "authors" in record:
        output["authors"] = list (map (format_author_record, record["authors"]))

    return output

def format_author_record_v3 (record):
    """Record formatter for the v3 authors API output."""
    email = None
    if conv.value_or (record, "is_editable", False):
        email = conv.value_or_none (record, "email")

    return {
        "uuid":        conv.value_or_none (record, "uuid"),
        "first_name":  conv.value_or_none(record, "first_name"),
        "last_name":   conv.value_or_none(record, "last_name"),
        "full_name":   conv.value_or_none(record, "full_name"),
        "email":       email,
        "orcid":       conv.value_or (record, "orcid_id", None),
        "is_editable": conv.value_or (record, "is_editable", False)
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

def file_download_url (record):
    """Returns a generated download_url or its default."""

    if "base_url" in record and not conv.value_or(record, "is_link_only", False):
        return f"{record['base_url']}/file/{record['container_uuid']}/{record['uuid']}"

    return conv.value_or_none(record, "download_url")

def format_file_for_dataset_record (record):
    """Record formatter for files."""
    download_url = file_download_url (record)
    output = {
      "id":            conv.value_or_none(record, "id"),
      "uuid":          conv.value_or_none(record, "uuid"),
      "name":          conv.value_or_none(record, "name"),
      "size":          conv.value_or_none(record, "size"),
      "is_link_only":  bool(conv.value_or_none(record, "is_link_only")),
      "is_incomplete": bool(conv.value_or_none(record, "is_incomplete")),
      "download_url":  download_url,
      "supplied_md5":  conv.value_or_none(record, "supplied_md5"),
      "computed_md5":  conv.value_or_none(record, "computed_md5"),
    }
    if "handle" in record:
        output["handle"] = record["handle"]

    return output

def format_file_details_record (record):
    """Detailed record formatter for files."""
    download_url = file_download_url (record)
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
      "download_url":  download_url,
      "supplied_md5":  conv.value_or_none(record, "supplied_md5"),
      "computed_md5":  conv.value_or_none(record, "computed_md5")
    }

def format_custom_field_record (record):
    """Record formatter for custom fields."""
    value = conv.value_or_none (record, "value")
    name  = conv.value_or_none (record, "name")
    if name is not None and name == "Data Link":
        value = [value]

    return { "name": name, "value": value }

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
    is_restricted = bool(conv.value_or (dataset, "is_restricted", False))
    if ((is_embargoed or is_restricted) and
        conv.value_or (dataset, "embargo_type", "") == "article" and
        not is_private):
        return {
            "embargo_date":      conv.value_or_none(dataset, "embargo_until_date"),
            "embargo_type":      conv.value_or_none(dataset, "embargo_type"),
            "embargo_title":     conv.value_or(dataset, "embargo_title", ""),
            "embargo_reason":    conv.value_or(dataset, "embargo_reason", ""),
        }

    embargo_option = None
    if is_restricted:
        embargo_option = { "id": 1000, "type": "restricted_access" }

    urls = dataset_urls (dataset)
    if "base_url" in dataset:
        for item in files:
            item['base_url'] = dataset['base_url']

    files_shown = []
    if not (is_embargoed or is_restricted):
        files_shown = list (map (format_file_for_dataset_record, files))

    return {
        "files":             files_shown,
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
        "is_embargoed":      bool(is_embargoed or is_restricted),
        "embargo_date":      conv.value_or_none(dataset, "embargo_until_date"),
        "embargo_type":      conv.value_or_none(dataset, "embargo_type"),
        "embargo_title":     conv.value_or(dataset, "embargo_title", ""),
        "embargo_reason":    conv.value_or(dataset, "embargo_reason", ""),
        "embargo_options":   [embargo_option] if embargo_option is not None else [],
        "id":                conv.value_or_none(dataset, "dataset_id"),
        "uuid":              conv.value_or_none(dataset, "container_uuid"),
        "title":             conv.value_or_none(dataset, "title"),
        "doi":               conv.value_or_none(dataset, "doi"),
        "handle":            conv.value_or(dataset, "handle", ""),
        "url":               conv.value_or_none(urls, "url"),
        "published_date":    conv.value_or_none(dataset, "published_date"),
        "thumb":             conv.value_or(dataset, "thumb", ""),
        "defined_type":      conv.value_or_none(dataset, "defined_type"),
        "defined_type_name": conv.value_or_none(dataset, "defined_type_name"),
        "group_id":          conv.value_or_none(dataset, "group_id"),
        "url_private_api":   conv.value_or_none(urls, "url_private_api"),
        "url_public_api":    conv.value_or_none(urls, "url_public_api"),
        "url_private_html":  conv.value_or_none(urls, "url_private_html"),
        "url_public_html":   conv.value_or_none(urls, "url_public_html"),
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

def format_dataset_embargo_record (dataset):
    """Record formatter for embargos."""

    is_embargoed = bool(conv.value_or (dataset, "is_embargoed", False))
    is_restricted = bool(conv.value_or (dataset, "is_restricted", False))

    embargo_options = []
    if is_restricted:
        embargo_options = [{ "id": 1000, "type": "restricted_access" }]

    return {
        "is_embargoed":      bool(is_embargoed or is_restricted),
        "embargo_date":      conv.value_or_none(dataset, "embargo_until_date"),
        "embargo_type":      conv.value_or(dataset, "embargo_type", "file"),
        "embargo_title":     conv.value_or(dataset, "embargo_title", ""),
        "embargo_reason":    conv.value_or(dataset, "embargo_reason", ""),

        # Embargo options are irrelevant outside of Figshare.
        "embargo_options":   embargo_options,
    }

def format_dataset_confidentiality_record (dataset):
    """Record formatter for confidentiality."""
    return {
        "is_confidential":   bool(conv.value_or_none(dataset, "is_confidential")),
        "reason": conv.value_or(dataset, "confidential_reason", ""),
    }

def format_collection_record (record):
    """Record formatter for collections."""
    urls = collection_urls (record)
    return {
        "id":                conv.value_or_none(record, "collection_id"),
        "uuid":              conv.value_or_none(record, "container_uuid"),
        "title":             conv.value_or_none(record, "title"),
        "doi":               conv.value_or_none(record, "doi"),
        "handle":            conv.value_or(record, "handle", ""),
        "url":               conv.value_or_none(urls, "url"),
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
    urls = collection_urls (collection)
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
        "url":               conv.value_or_none(urls, "url"),
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

def format_collection_version_record (record):
    """Record formatter for versions of collections."""
    version = conv.value_or_none (record, "version")
    urls    = collection_urls (record)
    return {
        "version": version,
        "url": f"{urls['url_public_api']}/versions/{version}"
    }

def format_dataset_version_record (record):
    """Record formatter for versions of datasets."""
    version = conv.value_or_none (record, "version")
    urls    = dataset_urls (record)
    return {
        "version": version,
        "url": f"{urls['url_public_api']}/versions/{version}"
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
      "is_featured":   conv.value_or_none(record, "is_featured")
    }

def format_review_record (record):
    """Record formatter for reviews."""
    return {
        "uuid":                  conv.value_or_none (record, "uuid"),
        "container_uuid":        conv.value_or_none (record, "container_uuid"),
        "dataset_title":         conv.value_or_none (record, "dataset_title"),
        "dataset_uuid":          conv.value_or_none (record, "dataset_uuid"),
        "dataset_version":       conv.value_or_none (record, "dataset_version"),
        "group_name":            conv.value_or_none (record, "group_name"),
        "has_published_version": conv.value_or_none (record, "has_published_version"),
        "last_seen_by_reviewer": conv.value_or_none (record, "last_seen_by_reviewer"),
        "modified_date":         conv.value_or_none (record, "modified_date"),
        "published_date":        conv.value_or_none (record, "published_date"),
        "request_date":          conv.value_or_none (record, "request_date"),
        "reviewer_email":        conv.value_or_none (record, "reviewer_email"),
        "reviewer_first_name":   conv.value_or_none (record, "reviewer_first_name"),
        "reviewer_last_name":    conv.value_or_none (record, "reviewer_last_name"),
        "status":                conv.value_or_none (record, "status"),
        "submitter_email":       conv.value_or_none (record, "submitter_email"),
        "submitter_first_name":  conv.value_or_none (record, "submitter_first_name"),
        "submitter_last_name":   conv.value_or_none (record, "submitter_last_name")
    }

def format_iiif_canvas_record (record, base_url):
    """Record formatter for an IIIF canvas."""
    width = 0
    height = 0
    iiif_image_context = None
    if "iiif_image_context" in record:
        iiif_image_context = record["iiif_image_context"]
        width = iiif_image_context["width"]
        height = iiif_image_context["height"]

    return {
        "id": f"{base_url}/iiif/v3/{record['uuid']}/canvas",
        "type": "Canvas",
        "label": { "none": [ record['name'] ] },
        "height": height,
        "width": width,
        "thumbnail": [{
            "id": f"{base_url}/iiif/v3/{record['uuid']}/full/max/0/default.jpg",
            "type": "Image",
            "format": "image/jpeg",
            "service": [ iiif_image_context ]
        }],
        "items": [{
            "id": f"{base_url}/iiif/v3/{record['uuid']}/annotationpage",
            "type": "AnnotationPage",
            "label": { "none": [ record['name'] ] },
            "items": [{
                "id": f"{base_url}/iiif/v3/{record['uuid']}/annotationpage/0",
                "type": "Annotation",
                "target": f"{base_url}/iiif/v3/{record['uuid']}/canvas",
                "body": {
                    "id": f"{base_url}/iiif/v3/{record['uuid']}/full/max/0/default.jpg",
                    "type": "Image",
                    "format": "image/jpeg",
                    "height": height,
                    "width": width,
                    "service": [ iiif_image_context ]
                }
            }]
        }]
    }

def format_iiif_manifest_record (dataset, files, authors, version, base_url):
    """Record formatter for IIIF manifests."""

    if version is None:
        version = "latest"

    metadata = []
    if authors:
        metadata = [{
            "label": { "en": [ "Authors" ] },
            "value": {
                "none": list (map (lambda author: conv.value_or_none (author, "full_name"), authors))
            }
        }]
    description = conv.value_or_none (dataset, "description")
    if description:
        metadata = metadata + [{
            "label": { "en": [ "Description" ] },
            "value": { "en": [ conv.html_to_plaintext (description) ] }
        }]
    items = list (map (lambda record: format_iiif_canvas_record (record, base_url), files))
    thumbnails = list(map (lambda item: item["thumbnail"][0], items))
    output = {
        "@context": "http://iiif.io/api/presentation/3/context.json",
        "id": f"{base_url}/iiif/v3/{dataset['container_uuid']}/{version}/manifest",
        "type": "Manifest",
        "label": { "en": [ f"IIIF Manifest for '{dataset['title']}'." ] },
        "metadata": metadata,
        "thumbnail": thumbnails,
        "items": items
    }
    return output
