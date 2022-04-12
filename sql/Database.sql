-- Note: Ensure the database uses UTF-8 multi-byte 4. Names can contain
-- characters from any language in the world. For example, use the following
-- statement to create the database:
-- CREATE DATABASE example_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-------------------------------------------------------------------------------
-- ARTICLES
-------------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS License(
    id                    INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    name                  VARCHAR(128),
    url                   TEXT) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS Timeline(
    id                    INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    posted                datetime,
    submission            datetime,
    revision              datetime,
    firstOnline           datetime,
    publisherPublication  datetime,
    publisherAcceptance   datetime) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS Institution(
    id                    INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    name                  TEXT) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS ArticleTag(
    id                    INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    tag                   TEXT,
    article_version_id    INT UNSIGNED) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS CollectionTag(
    id                    INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    tag                   TEXT,
    collection_version_id INT UNSIGNED) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS ArticlePrivateLink(
    id                    INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    id_string             TEXT,
    article_version_id    INT UNSIGNED,
    is_active             BOOLEAN NOT NULL DEFAULT 0,
    expires_date          DATETIME) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS CollectionPrivateLink(
    id                    INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    id_string             TEXT,
    collection_version_id INT UNSIGNED,
    is_active             BOOLEAN NOT NULL DEFAULT 0,
    expires_date          DATETIME) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS ArticleFunding(
    id                    INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    article_version_id    INT UNSIGNED,
    title                 TEXT,
    grant_code            TEXT,
    funder_name           TEXT,
    is_user_defined       BOOLEAN NOT NULL DEFAULT 0,
    url                   TEXT) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS CollectionFunding(
    id                    INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    collection_version_id INT UNSIGNED,
    title                 TEXT,
    grant_code            TEXT,
    funder_name           TEXT,
    is_user_defined       BOOLEAN NOT NULL DEFAULT 0,
    url                   TEXT) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS ArticleEmbargoOption(
    id                    INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    article_version_id    INT UNSIGNED,
    type                  VARCHAR(32),
    ip_name               TEXT) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS CollectionEmbargoOption(
    id                    INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    collection_version_id INT UNSIGNED,
    type                  VARCHAR(32),
    ip_name               TEXT) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS ArticleType(
    id                    INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    name                  TEXT
    ) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS ArticleEmbargo(
    id                    INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    date                  datetime,
    title                 TEXT,
    reason                TEXT) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS ArticleReference(
    id                    INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    article_version_id    INT UNSIGNED,
    url                   TEXT) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS CollectionReference(
    id                    INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    collection_version_id INT UNSIGNED,
    url                   TEXT) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS ArticleCategory(
    category_id           INT UNSIGNED,
    article_version_id    INT UNSIGNED) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS CollectionCategory(
    category_id           INT UNSIGNED,
    collection_version_id INT UNSIGNED) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS Article(
    article_version_id    INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,

    -- There can be multiple versions of an article. They all have the same
    -- article_id.
    article_id            INT UNSIGNED,
    account_id            INT UNSIGNED,
    title                 TEXT,
    doi                   TEXT,
    handle                TEXT,
    group_id              INT DEFAULT NULL,
    url                   TEXT,
    url_public_html       TEXT,
    url_public_api        TEXT,
    url_private_html      TEXT,
    url_private_api       TEXT,
    published_date        VARCHAR(32),
    timeline_id           INT UNSIGNED,
    thumb                 TEXT,
    defined_type          INT,
    defined_type_name     TEXT,
    figshare_url          TEXT,
    resource_title        TEXT,
    resource_doi          TEXT,
    embargo_options_id    INT UNSIGNED,
    citation              TEXT,
    confidential_reason   TEXT,
    embargo_type          TEXT,
    is_confidential       BOOLEAN NOT NULL DEFAULT 0,
    size                  BIGINT UNSIGNED,
    funding               TEXT,
    version               INT UNSIGNED,
    is_active             BOOLEAN NOT NULL DEFAULT 1,
    is_metadata_record    BOOLEAN NOT NULL DEFAULT 0,
    metadata_reason       TEXT,
    status                TEXT,
    description           TEXT,
    is_embargoed          BOOLEAN NOT NULL DEFAULT 0,
    embargo_date          DATETIME,
    is_public             BOOLEAN NOT NULL DEFAULT 1,
    modified_date         DATETIME,
    created_date          DATETIME,
    has_linked_file       BOOLEAN NOT NULL DEFAULT 0,
    license_id            INT UNSIGNED,
    embargo_title         TEXT,
    embargo_reason        TEXT,
    is_latest             BOOLEAN NOT NULL DEFAULT 0,
    is_editable           BOOLEAN NOT NULL DEFAULT 0,

    -- The following fields are inferred from the search interfaces
    -- rather than the data descriptions.  For example, an article
    -- must be linked to an institution somehow, but needs not
    -- necessarily be implemented using a foreign key.
    institution_id        INT UNSIGNED

    -- FOREIGN KEY (license_id) REFERENCES License(id)
    ) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS ArticleAuthor(
    id                    INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    article_version_id    INT UNSIGNED,
    author_id             INT UNSIGNED,
    order_index           INT UNSIGNED

    -- FOREIGN KEY (collection_version_id) REFERENCES Collection(id),
    -- FOREIGN KEY (author_id) REFERENCES Author(id),
    ) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS File(
    id                    INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    name                  TEXT,
    size                  BIGINT UNSIGNED,
    is_link_only          BOOLEAN NOT NULL DEFAULT 0,
    download_url          TEXT,
    supplied_md5          VARCHAR(64),
    computed_md5          VARCHAR(64),
    viewer_type           VARCHAR(64),
    preview_state         VARCHAR(64),
    status                VARCHAR(64),
    upload_url            TEXT,
    upload_token          TEXT) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS ArticleFile(
    id                    INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    article_version_id    INT UNSIGNED,
    file_id               INT UNSIGNED

    -- FOREIGN KEY (article_version_id) REFERENCES ArticleComplete(id),
    -- FOREIGN KEY (file_id) REFERENCES File(id),
    ) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS Author(
    id                    INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    institution_id        INT UNSIGNED,
    group_id              INT UNSIGNED,
    first_name            TEXT,
    last_name             TEXT,
    is_public             BOOLEAN NOT NULL DEFAULT 1,
    job_title             TEXT,

    -- Can this be inferred from first_name and last_name?
    full_name             TEXT,

    is_active             BOOLEAN NOT NULL DEFAULT 1,
    url_name              TEXT,
    orcid_id              TEXT) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS GroupEmbargoOptions(
    id                    INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    type                  ENUM('logged_in', 'ip_range', 'administrator'),
    ip_name               TEXT) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS Category(
    id                    INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    title                 TEXT,
    parent_id             INT UNSIGNED,
    source_id             INT UNSIGNED,
    taxonomy_id           INT UNSIGNED) ENGINE=InnoDB;

-------------------------------------------------------------------------------
-- COLLECTIONS
-------------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS Collection(
    collection_version_id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    collection_id         INT UNSIGNED,
    title                 TEXT,
    doi                   TEXT,
    handle                TEXT,
    url                   TEXT,
    citation              TEXT,
    description           TEXT,
    group_id              INT UNSIGNED,
    institution_id        INT UNSIGNED,
    timeline_id           INT UNSIGNED,
    account_id            INT UNSIGNED,
    published_date        DATETIME,
    modified_date         DATETIME,
    created_date          DATETIME,
    version               INT UNSIGNED,
    resource_id           INT UNSIGNED,
    resource_doi          TEXT,
    resource_title        TEXT,
    resource_link         TEXT,
    resource_version      INT UNSIGNED,
    articles_count        INT UNSIGNED,
    group_resource_id     INT UNSIGNED,
    is_latest             BOOLEAN NOT NULL DEFAULT 0,
    is_editable           BOOLEAN NOT NULL DEFAULT 0,
    is_public             BOOLEAN NOT NULL DEFAULT 0

    -- FOREIGN KEY (institution_id) REFERENCES Institution(id),
    -- FOREIGN KEY (timeline_id) REFERENCES Timeline(id)
    ) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS CollectionAuthor(
    id                    INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    collection_version_id INT UNSIGNED,
    author_id             INT UNSIGNED,
    order_index           INT UNSIGNED

    -- FOREIGN KEY (collection_version_id) REFERENCES Collection(id),
    -- FOREIGN KEY (author_id) REFERENCES Author(id),
    ) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS CollectionArticle(
    id                    INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    collection_version_id INT UNSIGNED,
    article_id            INT UNSIGNED) ENGINE=InnoDB;

-------------------------------------------------------------------------------
-- PROJECTS
-------------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS Project(
    id                    INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    account_id            INT UNSIGNED,
    title                 TEXT,
    url                   TEXT,
    published_date        DATETIME) ENGINE=InnoDB;

-------------------------------------------------------------------------------
-- INSTITUTIONS
-------------------------------------------------------------------------------

-- See table Institution above.

-------------------------------------------------------------------------------
-- AUTHORS
-------------------------------------------------------------------------------

-- See table Author above.

-------------------------------------------------------------------------------
-- ACCOUNTS
-------------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS Account(
    id                    INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    active                INT,
    created_date          DATETIME,
    email                 TEXT,
    first_name            TEXT,
    group_id              INT,
    institution_id        INT,
    institution_user_id   TEXT,
    last_name             TEXT,
    maximum_file_size     INT,
    modified_date         DATETIME,
    pending_quota_request BOOLEAN NOT NULL DEFAULT 0,
    quota                 INT,
    used_quota            INT,
    used_quota_private    INT,
    used_quota_public     INT) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS ArticleCustomField(
    id                    INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    article_version_id    INT UNSIGNED,
    name                  TEXT,
    value                 TEXT,
    default_value         TEXT,
    placeholder           TEXT,
    max_length            INT UNSIGNED,
    min_length            INT UNSIGNED,
    field_type            VARCHAR(128),
    is_multiple           BOOLEAN NOT NULL DEFAULT 0,
    is_mandatory          BOOLEAN NOT NULL DEFAULT 0) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS ArticleCustomFieldOption(
    id                      INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    article_custom_field_id INT UNSIGNED,
    value                   TEXT) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS CollectionCustomField(
    id                    INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    collection_version_id INT UNSIGNED,
    name                  TEXT,
    value                 TEXT,
    default_value         TEXT,
    placeholder           TEXT,
    max_length            INT UNSIGNED,
    min_length            INT UNSIGNED,
    field_type            VARCHAR(128),
    is_multiple           BOOLEAN NOT NULL DEFAULT 0,
    is_mandatory          BOOLEAN NOT NULL DEFAULT 0) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS CollectionCustomFieldOption(
    id                         INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    collection_custom_field_id INT UNSIGNED,
    value                      TEXT) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS ArticleTotals(
    article_id            INT UNSIGNED,
    views                 INT UNSIGNED,
    downloads             INT UNSIGNED,
    shares                INT UNSIGNED,
    cites                 INT UNSIGNED,
    created_at            DATETIME) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS ArticleViews(
    article_id            INT UNSIGNED,
    country               TEXT,
    region                TEXT,
    views                 INT UNSIGNED,
    date                  DATETIME) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS ArticleDownloads(
    article_id            INT UNSIGNED,
    country               TEXT,
    region                TEXT,
    downloads             INT UNSIGNED,
    date                  DATETIME) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS ArticleShares(
    article_id            INT UNSIGNED,
    country               TEXT,
    region                TEXT,
    shares                INT UNSIGNED,
    date                  DATETIME) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS CollectionTotals(
    collection_id         INT UNSIGNED,
    views                 INT UNSIGNED,
    downloads             INT UNSIGNED,
    shares                INT UNSIGNED,
    cites                 INT UNSIGNED,
    created_at            DATETIME) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS CollectionViews(
    collection_id         INT UNSIGNED,
    country               TEXT,
    region                TEXT,
    views                 INT UNSIGNED,
    date                  DATETIME) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS CollectionDownloads(
    collection_id         INT UNSIGNED,
    country               TEXT,
    region                TEXT,
    downloads             INT UNSIGNED,
    date                  DATETIME) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS CollectionShares(
    collection_id         INT UNSIGNED,
    country               TEXT,
    region                TEXT,
    shares                INT UNSIGNED,
    date                  DATETIME) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS InstitutionGroup(
    id                    INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    parent_id             INT UNSIGNED,
    resource_id           TEXT,
    name                  TEXT,
    association_criteria  TEXT) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS Session(
    id                    INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    token                 VARCHAR(65),
    account_id            INT UNSIGNED,
    may_impersonate       BOOLEAN NOT NULL DEFAULT 0,
    created_at            DATETIME DEFAULT NOW()) ENGINE=InnoDB;
