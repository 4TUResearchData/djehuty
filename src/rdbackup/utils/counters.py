"""
This module provides an atomic ID iterator.
"""

from multiprocessing import Value

class IdGenerator:
    """
    This class implements atomic ID iterators to make the
    relational database style of assigning numeric IDs to records
    work for the RDF model.

    This class implements atomic iterators for the lifetime of a
    single run, so the user must set the initial state _before_
    serving/performing any state-changing operations.
    """

    def __init__ (self):
        self.article_id          = Value('i', 0)
        self.article_category_id = Value('i', 0)
        self.article_author_id   = Value('i', 0)
        self.collection_id       = Value('i', 0)
        self.author_id           = Value('i', 0)
        self.account_id          = Value('i', 0)
        self.file_id             = Value('i', 0)
        self.category_id         = Value('i', 0)
        self.project_id          = Value('i', 0)
        self.timeline_id         = Value('i', 0)
        self.institution_id      = Value('i', 0)
        self.tag_id              = Value('i', 0)

    ## ------------------------------------------------------------------------
    ## ARTICLES
    ## ------------------------------------------------------------------------

    def set_article_id (self, article_id):
        """Procedure to set the current value of ARTICLE_ID."""
        self.article_id.value = article_id
        return True

    def next_article_id (self):
        """Returns the next ARTICLE_ID value to assign to an article."""
        self.article_id.value += 1
        return self.article_id.value

    def current_article_id (self):
        """Returns the current ARTICLE_ID value."""
        return self.article_id.value

    ## ------------------------------------------------------------------------
    ## COLLECTIONS
    ## ------------------------------------------------------------------------

    def set_collection_id (self, collection_id):
        """Procedure to set the current value of COLLECTION_ID."""
        self.collection_id.value = collection_id
        return True

    def next_collection_id (self):
        """Returns the next COLLECTION_ID value to assign to a collection."""
        self.collection_id.value += 1
        return self.collection_id.value

    def current_collection_id (self):
        """Returns the current COLLECTION_ID value."""
        return self.collection_id.value

    ## ------------------------------------------------------------------------
    ## AUTHORS
    ## ------------------------------------------------------------------------

    def set_author_id (self, author_id):
        """Procedure to set the current value of AUTHOR_ID."""
        self.author_id.value = author_id
        return True

    def next_author_id (self):
        """Returns the next AUTHOR_ID value to assign to a author."""
        self.author_id.value += 1
        return self.author_id.value

    def current_author_id (self):
        """Returns the current AUTHOR_ID value."""
        return self.author_id.value

    ## ------------------------------------------------------------------------
    ## ACCOUNTS
    ## ------------------------------------------------------------------------

    def set_account_id (self, account_id):
        """Procedure to set the current value of ACCOUNT_ID."""
        self.account_id.value = account_id
        return True

    def next_account_id (self):
        """Returns the next ACCOUNT_ID value to assign to a account."""
        self.account_id.value += 1
        return self.account_id.value

    def current_account_id (self):
        """Returns the current ACCOUNT_ID value."""
        return self.account_id.value

    ## ------------------------------------------------------------------------
    ## FILES
    ## ------------------------------------------------------------------------

    def set_file_id (self, file_id):
        """Procedure to set the current value of FILE_ID."""
        self.file_id.value = file_id
        return True

    def next_file_id (self):
        """Returns the next FILE_ID value to assign to a file."""
        self.file_id.value += 1
        return self.file_id.value

    def current_file_id (self):
        """Returns the current FILE_ID value."""
        return self.file_id.value

    ## ------------------------------------------------------------------------
    ## CATEGORIES
    ## ------------------------------------------------------------------------

    def set_category_id (self, category_id):
        """Procedure to set the current value of CATEGORY_ID."""
        self.category_id.value = category_id
        return True

    def next_category_id (self):
        """Returns the next CATEGORY_ID value to assign to a category."""
        self.category_id.value += 1
        return self.category_id.value

    def current_category_id (self):
        """Returns the current CATEGORY_ID value."""
        return self.category_id.value

    ## ------------------------------------------------------------------------
    ## PROJECTS
    ## ------------------------------------------------------------------------

    def set_project_id (self, project_id):
        """Procedure to set the current value of PROJECT_ID."""
        self.project_id.value = project_id
        return True

    def next_project_id (self):
        """Returns the next PROJECT_ID value to assign to a project."""
        self.project_id.value += 1
        return self.project_id.value

    def current_project_id (self):
        """Returns the current PROJECT_ID value."""
        return self.project_id.value

    ## ------------------------------------------------------------------------
    ## TIMELINES
    ## ------------------------------------------------------------------------

    def set_timeline_id (self, timeline_id):
        """Procedure to set the current value of TIMELINE_ID."""
        self.timeline_id.value = timeline_id
        return True

    def next_timeline_id (self):
        """Returns the next TIMELINE_ID value to assign to a timeline."""
        self.timeline_id.value += 1
        return self.timeline_id.value

    def current_timeline_id (self):
        """Returns the current TIMELINE_ID value."""
        return self.timeline_id.value

    ## ------------------------------------------------------------------------
    ## INSTITUTIONS
    ## ------------------------------------------------------------------------

    def set_institution_id (self, institution_id):
        """Procedure to set the current value of INSTITUTION_ID."""
        self.institution_id.value = institution_id
        return True

    def next_institution_id (self):
        """Returns the next INSTITUTION_ID value to assign to a institution."""
        self.institution_id.value += 1
        return self.institution_id.value

    def current_institution_id (self):
        """Returns the current INSTITUTION_ID value."""
        return self.institution_id.value

    ## ------------------------------------------------------------------------
    ## TAGS
    ## ------------------------------------------------------------------------

    def set_tag_id (self, tag_id):
        """Procedure to set the current value of TAG_ID."""
        self.tag_id.value = tag_id
        return True

    def next_tag_id (self):
        """Returns the next TAG_ID value to assign to a tag."""
        self.tag_id.value += 1
        return self.tag_id.value

    def current_tag_id (self):
        """Returns the current TAG_ID value."""
        return self.tag_id.value

    ## ------------------------------------------------------------------------
    ## ARTICLE_CATEGORIES
    ## ------------------------------------------------------------------------

    def set_article_category_id (self, article_category_id):
        """Procedure to set the current value of ARTICLE_CATEGORY_ID."""
        self.article_category_id.value = article_category_id
        return True

    def next_article_category_id (self):
        """Returns the next ARTICLE_CATEGORY_ID value to assign to an article_category."""
        self.article_category_id.value += 1
        return self.article_category_id.value

    def current_article_category_id (self):
        """Returns the current ARTICLE_CATEGORY_ID value."""
        return self.article_category_id.value

    ## ------------------------------------------------------------------------
    ## ARTICLE_AUTHORS
    ## ------------------------------------------------------------------------

    def set_article_author_id (self, article_author_id):
        """Procedure to set the current value of ARTICLE_AUTHOR_ID."""
        self.article_author_id.value = article_author_id
        return True

    def next_article_author_id (self):
        """Returns the next ARTICLE_AUTHOR_ID value to assign to an article_author."""
        self.article_author_id.value += 1
        return self.article_author_id.value

    def current_article_author_id (self):
        """Returns the current ARTICLE_AUTHOR_ID value."""
        return self.article_author_id.value

    ## ------------------------------------------------------------------------
    ## ARTICLE_FILES
    ## ------------------------------------------------------------------------

    def set_article_file_id (self, article_file_id):
        """Procedure to set the current value of ARTICLE_FILE_ID."""
        self.article_file_id.value = article_file_id
        return True

    def next_article_file_id (self):
        """Returns the next ARTICLE_FILE_ID value to assign to an article_file."""
        self.article_file_id.value += 1
        return self.article_file_id.value

    def current_article_file_id (self):
        """Returns the current ARTICLE_FILE_ID value."""
        return self.article_file_id.value
