-------------------------------------------------------------------------------
-- ARTICLES
-------------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS License(
    id                    INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    name                  VARCHAR(128),
    url                   VARCHAR(255)) ENGINE=InnoDB;

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
    name                  VARCHAR(255)) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS Tag(
    id                    INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    tag                   VARCHAR(255),
    article_id            INT UNSIGNED) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS ArticleEmbargoOptionGroup(
    id                    INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    name                  VARCHAR(255)) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS ArticleEmbargoOption(
    id                    INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    type                  VARCHAR(32),
    ip_name               VARCHAR(255),
    group_id              INT UNSIGNED

    -- FOREIGN KEY (group_id) REFERENCES ArticleEmbargoOptionGroup(id)
    ) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS ArticleType(
    id                    INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    name                  VARCHAR(255)
    ) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS ArticleEmbargo(
    id                    INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    date                  datetime,
    title                 VARCHAR(255),
    reason                VARCHAR(255)) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS ArticleReference(
    id                    INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    article_id            INT UNSIGNED,
    url                   VARCHAR(255)
    ) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS ArticleCategory(
    category_id           INT UNSIGNED,
    article_id            INT UNSIGNED) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS ArticleVersion(
    article_id            INT UNSIGNED,
    version               INT UNSIGNED,

    -- This field can be auto-generated.
    url                   VARCHAR(255)) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS Article(
    id                    INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    account_id            INT UNSIGNED,
    title                 VARCHAR(255),
    doi                   VARCHAR(255),
    handle                VARCHAR(255),
    group_id              INT DEFAULT NULL,
    url                   VARCHAR(255),
    url_public_html       VARCHAR(255),
    url_public_api        VARCHAR(255),
    url_private_html      VARCHAR(255),
    url_private_api       VARCHAR(255),
    published_date        VARCHAR(32),
    timeline_id           INT UNSIGNED,
    thumb                 VARCHAR(255),
    defined_type          INT,
    defined_type_name     VARCHAR(255),
    figshare_url          VARCHAR(255),
    resource_title        VARCHAR(255),
    resource_doi          VARCHAR(255),
    embargo_options_id    INT UNSIGNED,
    citation              TEXT,
    confidential_reason   VARCHAR(255),
    embargo_type          VARCHAR(255),
    is_confidential       BOOLEAN NOT NULL DEFAULT 0,
    size                  BIGINT UNSIGNED,
    funding               VARCHAR(255),
    funding_id            INT UNSIGNED,
    version               INT UNSIGNED,
    is_active             BOOLEAN NOT NULL DEFAULT 1,
    is_metadata_record    BOOLEAN NOT NULL DEFAULT 0,
    metadata_reason       VARCHAR(255),
    status                VARCHAR(255),
    description           TEXT,
    is_embargoed          BOOLEAN NOT NULL DEFAULT 0,
    embargo_date          DATETIME,
    is_public             BOOLEAN NOT NULL DEFAULT 1,
    modified_date         DATETIME,
    created_date          DATETIME,
    has_linked_file       BOOLEAN NOT NULL DEFAULT 0,
    license_id            INT UNSIGNED,
    embargo_title         VARCHAR(255),
    embargo_reason        VARCHAR(255),

    -- The following fields are inferred from the search interfaces
    -- rather than the data descriptions.  For example, an article
    -- must be linked to an institution somehow, but needs not
    -- necessarily be implemented using a foreign key.
    institution_id        INT UNSIGNED

    -- FOREIGN KEY (license_id) REFERENCES License(id)
    ) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS ArticleAuthor(
    id                    INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    article_id            INT UNSIGNED,
    author_id             INT UNSIGNED

    -- FOREIGN KEY (collection_id) REFERENCES Collection(id),
    -- FOREIGN KEY (author_id) REFERENCES Author(id),
    ) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS File(
    id                    INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    name                  VARCHAR(255),
    size                  BIGINT UNSIGNED,
    is_link_only          BOOLEAN NOT NULL DEFAULT 0,
    download_url          VARCHAR(255),
    supplied_md5          VARCHAR(64),
    computed_md5          VARCHAR(64),
    viewer_type           VARCHAR(64),
    preview_state         VARCHAR(64),
    status                VARCHAR(64),
    upload_url            VARCHAR(255),
    upload_token          VARCHAR(255)) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS ArticleFile(
    id                    INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    article_id            INT UNSIGNED,
    file_id               INT UNSIGNED

    -- FOREIGN KEY (article_id) REFERENCES ArticleComplete(id),
    -- FOREIGN KEY (file_id) REFERENCES File(id),
    ) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS Author(
    id                    INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    institution_id        INT UNSIGNED,
    group_id              INT UNSIGNED,
    first_name            VARCHAR(255),
    last_name             VARCHAR(255),
    is_public             BOOLEAN NOT NULL DEFAULT 1,
    job_title             VARCHAR(255),

    -- Can this be inferred from first_name and last_name?
    full_name             VARCHAR(255),

    is_active             BOOLEAN NOT NULL DEFAULT 1,
    url_name              VARCHAR(255),
    orcid_id              VARCHAR(255)) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS CustomArticleField(
    id                    INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    name                  VARCHAR(255),
    value                 VARCHAR(255),
    is_mandatory          BOOLEAN NOT NULL DEFAULT 0) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS GroupEmbargoOptions(
    id                    INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    type                  ENUM('logged_in', 'ip_range', 'administrator'),
    ip_name               VARCHAR(255)) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS Category(
    id                    INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    parent_id             INT UNSIGNED,
    title                 VARCHAR(255)) ENGINE=InnoDB;

-------------------------------------------------------------------------------
-- COLLECTIONS
-------------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS Collection(
    id                    INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    title                 VARCHAR(255),
    doi                   VARCHAR(255),
    handle                VARCHAR(255),
    url                   VARCHAR(255),
    citation              TEXT,
    description           TEXT,
    group_id              INT UNSIGNED,
    institution_id        INT UNSIGNED,
    timeline_id           INT UNSIGNED,
    account_id            INT UNSIGNED,
    published_date        DATETIME,
    modified_date         DATETIME,
    created_date          DATETIME

    -- FOREIGN KEY (institution_id) REFERENCES Institution(id),
    -- FOREIGN KEY (timeline_id) REFERENCES Timeline(id)
    ) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS CollectionAuthors(
    id                    INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    collection_id         INT UNSIGNED,
    author_id             INT UNSIGNED

    -- FOREIGN KEY (collection_id) REFERENCES Collection(id),
    -- FOREIGN KEY (author_id) REFERENCES Author(id),
    ) ENGINE=InnoDB;

-------------------------------------------------------------------------------
-- PROJECTS
-------------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS Project(
    id                    INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    account_id            INT UNSIGNED,
    title                 VARCHAR(255),
    url                   VARCHAR(255),
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
    email                 VARCHAR(255),
    first_name            VARCHAR(255),
    group_id              INT,
    institution_id        INT,
    institution_user_id   VARCHAR(255),
    last_name             VARCHAR(255),
    maximum_file_size     INT,
    modified_date         DATETIME,
    pending_quota_request BOOLEAN NOT NULL DEFAULT 0,
    quota                 INT,
    used_quota            INT,
    used_quota_private    INT,
    used_quota_public     INT) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS ArticleCustomField(
    id                    INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    article_id            INT UNSIGNED,
    name                  VARCHAR(255),
    value                 TEXT,
    default_value         TEXT,
    placeholder           TEXT,
    max_length            INT UNSIGNED,
    min_length            INT UNSIGNED,
    field_type            VARCHAR(128),
    is_multiple           BOOLEAN NOT NULL DEFAULT 0,
    is_mandatory          BOOLEAN NOT NULL DEFAULT 0) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS ArticleStatistics(
    article_id            INT UNSIGNED,
    views                 INT UNSIGNED,
    downloads             INT UNSIGNED,
    shares                INT UNSIGNED,
    date                  DATETIME) ENGINE=InnoDB;
