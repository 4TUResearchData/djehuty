# Configuring `djehuty`

Now that `djehuty` is installed, it's a good moment to look into its run-time
configuration options. All configuration can be done through a configuration
file. A JSON example is available at `etc/djehuty/djehuty-example-config.json`.

> **Note:** XML configuration is deprecated and will be removed in December 2026.
> Migrate to JSON (see `etc/djehuty/djehuty-example-config.json`).

## Essential options

| Option | Description |
|--------|-------------|
| `bind-address` | The address to bind a TCP socket on. |
| `port` | The port to bind a TCP socket on. |
| `alternative-port` | A fall-back port to bind on when `port` is already in use. |
| `base-url` | The URL on which the instance will be available to the outside world. |
| `log-file` | Path to a file where log output is written. When omitted, logs go to stdout. |
| `allow-crawlers` | Set to 1 to allow crawlers in the `robots.txt`, otherwise set to 0. |
| `production` | Performs extra checks before starting. Enable this when running a production instance. |
| `live-reload` | When set to 1, it reloads Python code on-the-fly. We recommend to set it to 0 when running in production. |
| `debug-mode` | When set to 1, it will display backtraces and error messages in the web browser. When set to 0, it will only show backtraces and error messages in the web browser. |
| `use-x-forwarded-for` | When running `djehuty` behind a reverse-proxy server, use the HTTP header `X-Forwarded-For` to log IP address information. Set to 1 when `djehuty` should use the `X-Forwarded-For` HTTP header. |
| `static-resources-cache` | When running `djehuty` behind a reverse-proxy server, it can write images, fonts, stylesheets and JavaScript resources to a folder so it can be served by the reverse-proxy server. Specify a filesystem directory to store the resources at. |
| `disable-collaboration` | When set to 1, it disables the "collaborators" feature. |
| `allowed-depositing-domains` | When unset, any authenticated user may deposit data. Otherwise, this option limits the ability to deposit to users with an e-mail address of the listed domain names. |
| `cache-root` | `djehuty` can cache query responses to lower the load on the database server. Specify the directory where to store cache files. This element takes an attribute `clear-on-start`, and when set to 1, it will remove all cache files on start-up of `djehuty`. |
| `profile-images-root` | Users can upload a profile image in `djehuty`. This option should point to a filesystem directory where these profile images can be stored. |
| `disable-2fa` | Accounts with privileges receive a code by e-mail as a second factor when logging in. Setting this option to 1 disables the second factor authentication. |
| `sandbox-message` | Display a message on the top of every page. |
| `notice-message` | Display a message on the main page. |
| `maintenance-mode` | When set to 1, all HTTP requests result in the displayment of a maintenance message. Use this option while backing up the database, or when performing major updates. |

## Configuring the Database

The `djehuty` program stores its state in a SPARQL 1.1 compliant RDF store.
Configuring the connection details is done in the `rdf-store` node.

| Option | Description |
|--------|-------------|
| `state-graph` | The graph name to store triplets in. |
| `sparql-uri` | The URI at which the SPARQL 1.1 endpoint can be reached. When the `sparql-uri` begins with `bdb://`, followed by a path to a filesystem directory, it will use the BerkeleyDB back-end, for which the `berkeleydb` Python package needs to be installed. |
| `sparql-update-uri` | The URI at which the SPARQL 1.1 Update endpoint can be reached (in case it is different from the `sparql-uri`). |

## Audit trails and database reconstruction

The `djehuty` program can keep an audit log of all database modifications made
by itself from which a database state can be reconstructed. Whether `djehuty`
keeps such an audit log can be configured with the following option:

| Option | Description |
|--------|-------------|
| `enable-query-audit-log` | When set to 1, it writes every SPARQL query that modifies the database in the web logs. This can be replayed to reconstruct the database at a later time. Setting this option to 0 disables this feature. This element takes an attribute `transactions-directory` that should specify an empty directory to which transactions can be written that are extracted from the audit log. |

### Reconstructing the database from the query audit log

Each query that modifies the database state while the query audit logs are
enabled can be extracted from the query audit log using the
`--extract-transactions-from-log` command-line option. A timestamp to specify
the starting point to extract from can be specified as an argument. The
following example displays its use:

```bash
djehuty web --config-file=config.xml --extract-transactions-from-log="YYYY-MM-DD HH:MM:SS"
```

This will create a file for each query in the folder specified in the
`transactions-directory` attribute.

To replay the extracted transactions, use the `--apply-transactions`
command-line option:

```bash
djehuty web --config-file=config.xml --apply-transactions
```

When a query cannot be executed, the command stops, allowing to fix or remove
the query to-be-replayed. Invoking `--apply-transactions` a second time will
continue replaying where the previous run stopped.

## Configuring storage

Storage locations can be configured with the `storage` node. When configuring
multiple locations, `djehuty` attempts to find a file by looking at the first
configured location, and in case it cannot find the file there, it will look at
the second configured location, and so on, until it has tried each storage
location.

This allows for moving files between storage systems transparently without
requiring specific interactions with `djehuty` other than having the files made
available as a POSIX filesystem or in an S3 bucket.

One use-case that suits this mechanism is letting uploads write to fast online
storage and later move the uploaded files to a slower but less costly storage.

| Option | Description |
|--------|-------------|
| `storage-root` | The primary filesystem path where files, cache, and profile images are stored. Sub-directories are created automatically. |
| `location` | A filesystem path to where files are stored. This is a repeatable property. |
| `s3-bucket` | An S3 bucket configuration. See [Configuring S3 buckets](#configuring-s3-buckets). This is a repeatable property. |

### Configuring S3 buckets

Other than configuring storage locations on a POSIX filesystem, `djehuty` can
be configured to serve files from an S3 bucket. To do so, the following
parameters must be configured within a `s3-bucket` node.

| Option | Description |
|--------|-------------|
| `endpoint` | Endpoint URL to connect to. |
| `name` | Name of the bucket. |
| `key-id` | Key ID for the bucket. |
| `secret-key` | Secret key for the bucket. |

For example, configuring one filesystem location and one S3 bucket as storage
locations looks as following:

```xml
<storage>
  <location>/data</location>
  <s3-bucket>
    <endpoint>https://some.example</endpoint>
    <name>example-bucket</name>
    <key-id>...</key-id>
    <secret-key>...</secret-key>
  </s3-bucket>
</storage>
```

There are a few scenarios in which `djehuty` downloads an S3 object to perform
some operation on: creating thumbnails and IIIF image transformations. To direct
where these temporary files will be stored, the `s3-cache-root` can be
configured.

| Option | Description |
|--------|-------------|
| `s3-cache-root` | The directory to store the S3 objects while performing some operation on the objects. This option can only be configured globally and applies to all S3 buckets. |

## Configuring an identity provider

Ideally, `djehuty` makes use of an external identity provider. `djehuty` can
use SAML2.0, ORCID, or an internal identity provider (for testing and
development purposes only).

This section will outline the configuration options for each identity provision
mechanism.

### SAML2.0

For SAML 2.0, the configuration can be placed in the `saml` section under
`authentication`. That looks as following:

```xml
<authentication>
  <saml version="2.0">
    <!-- Configuration goes here. -->
  </saml>
</authentication>
```

The options outlined in the remainder of this section should be placed where the
example shows `<!-- Configuration goes here. -->`.

| Option | Description |
|--------|-------------|
| `strict` | When set to 1, SAML responses must be signed. **Never disable `strict` mode in a production environment.** |
| `debug` | Increases logging verbosity for SAML-related messages. |
| `attributes` | In this section the attributes provided by the identity provider can be aligned to the attributes `djehuty` expects. |
| `service-provider` | The `djehuty` program fulfills the role of service provider. In this section the certificate and service provider metadata can be configured. |
| `identity-provider` | In this section the certificate and single-sign-on URL of the identity provider can be configured. |
| `sram` | In this section, SURF Research Access Management-specific attributes can be configured. |

#### The `attributes` configuration

To create account and author records and to authenticate a user, `djehuty`
stores information provided by the identity provider. Each identity provider may
provide this information using different attributes. Therefore, the translation
from attributes used by `djehuty` and attributes given by the identity provider
can be configured. The following attributes must be configured.

| Option | Description |
|--------|-------------|
| `first-name` | A user's first name. |
| `last-name` | A user's last name. |
| `common-name` | A user's full name. |
| `email` | A user's e-mail address. |
| `groups` | The attribute denoting groups. |
| `group-prefix` | The prefix for each group short name. |

As an example, the attributes configuration for SURFConext looks like this:

```xml
<attributes>
  <first-name>urn:mace:dir:attribute-def:givenName</first-name>
  <last-name>urn:mace:dir:attribute-def:sn</last-name>
  <common-name>urn:mace:dir:attribute-def:cn</common-name>
  <email>urn:mace:dir:attribute-def:mail</email>
</attributes>
```

And for SURF Research Access Management (SRAM), the attributes configuration
looks like this:

```xml
<attributes>
  <first-name>urn:oid:2.5.4.42</first-name>
  <last-name>urn:oid:2.5.4.4</last-name>
  <common-name>urn:oid:2.5.4.3</common-name>
  <email>urn:oid:0.9.2342.19200300.100.1.3</email>
  <groups>urn:oid:1.3.6.1.4.1.5923.1.1.1.7</groups>
  <group-prefix>urn:mace:surf.nl:sram:group:[organisation]:[service]</group-prefix>
</attributes>
```

#### The `sram` configuration

When using SURF Research Access Management (SRAM), `djehuty` can persuade SRAM
to send an invitation to anyone inside or outside the institution to join the
SRAM collaboration that provides access to the `djehuty` instance. To do so,
the following attributes must be configured.

| Option | Description |
|--------|-------------|
| `organization-api-token` | An organization-level API token. |
| `collaboration-id` | The UUID of the collaboration to invite users to. |

#### The `service-provider` configuration

| Option | Description |
|--------|-------------|
| `x509-certificate` | Contents of the public certificate without whitespacing. |
| `private-key` | Contents of the private key belonging to the `x509-certificate` to sign messages with. |
| `metadata` | This section contains metadata that may be displayed by the identity provider to users before authorizing them. |
| → `display-name` | The name to be displayed by the identity provider when authorizing the user to the service. |
| → `url` | The URL to the service. |
| → `description` | Textual description of the service. |
| → `organization` | This section contains metadata to describe the organization behind the service. |
| → → `name` | The name of the service provider's organization. |
| → → `url` | The URL to the web page of the organization. |
| → `contact` | A repeatable section to list contact persons and their roles within the organization. The role can be configured by setting the `type` attribute. |
| → → `first-name` | The first name of the contact person. |
| → → `last-name` | The last name of the contact person. |
| → → `email` | The e-mail address of the contact person. Note that some identity providers prefer functional e-mail addresses (e.g. support@... instead of jdoe@...). |

### ORCID

[ORCID.org](https://orcid.org) plays a key role in making researchers findable.
Its identity provider service can be used by `djehuty` in two ways:

1. As primary identity provider to log in and deposit data;
2. As additional identity provider to couple an author record to its ORCID record.

When another identity provider is configured in addition to ORCID, that identity
provider will be used as primary and ORCID will only be used to couple author
records to the author's ORCID record.

To configure ORCID, the configuration can be placed in the `orcid` section
under `authentication`. That looks as following:

```xml
<authentication>
  <orcid>
    <!-- Configuration goes here. -->
  </orcid>
</authentication>
```

Then the following parameters can be configured:

| Option | Description |
|--------|-------------|
| `client-id` | The client ID provided by ORCID. |
| `client-secret` | The client secret provided by ORCID. |
| `endpoint` | The URL to the ORCID endpoint to use. |

## Configuring an e-mail server

On various occasions, `djehuty` will attempt to send an e-mail to either an
author, a reviewer or an administrator. To be able to do so, an e-mail server
must be configured from which the instance may send e-mails.

The configuration is done under the `email` node, and the following items can
be configured:

| Option | Description |
|--------|-------------|
| `server` | Address of the e-mail server without protocol specification. |
| `port` | The port the e-mail server operates on. |
| `starttls` | When 1, `djehuty` attempts to use StartTLS. |
| `username` | The username to authenticate with to the e-mail server. |
| `password` | The password to authenticate with to the e-mail server. |
| `from` | The e-mail address used to send e-mail from. |
| `subject-prefix` | Text to prefix in the subject of all e-mails sent from the instance of `djehuty`. This can be used to distinguish a test instance from a production instance. |

## Configuring DOI registration

When publishing a dataset or collection, `djehuty` can register a persistent
identifier with DataCite. To enable this feature, configure it under the
`datacite` node. The following parameters can be configured:

| Option | Description |
|--------|-------------|
| `api-url` | The URL of the API endpoint of DataCite. |
| `repository-id` | The repository identifier given by DataCite. |
| `password` | The password to authenticate with to DataCite. |
| `prefix` | The DOI prefix to use when registering a DOI. |

## Configuring Handle registration

Each uploaded file can be assigned a persistent identifier using the Handle
system. To enable this feature, configure it under the `handle` node. The
following parameters can be configured:

| Option | Description |
|--------|-------------|
| `url` | The URL of the API endpoint of the Handle system implementor. |
| `certificate` | Certificate to use for authenticating to the endpoint. |
| `private-key` | The private key paired with the certificate used to authenticate to the endpoint. |
| `prefix` | The Handle prefix to use when registering a handle. |
| `index` | The index to use when registering a handle. |

## Configuring IIIF support

When publishing images, `djehuty` can enable the IIIF Image API for the images.
It uses `libvips` and `pyvips` under the hood to perform image manipulation. The
following parameters can be configured:

| Option | Description |
|--------|-------------|
| `enable-iiif` | Enable support for the IIIF image API. This requires the `pyvips` package to be available in the run-time environment. |
| `iiif-cache-root` | The directory to store the output of IIIF Image API requests to avoid re-computing the image. |

## Configuring CODECHECK requests

When publishing software, `djehuty` can be configured to offer reproducibility
check. Once enabled, the metadata form will include an option to request a
reproducibility check or provide a CODECHECK certificate. The option will be
visible for the groups for which the `is_featured` parameter is set to True. The
following parameter can be configured:

| Option | Description |
|--------|-------------|
| `enable-codecheck` | Enable CODECHECK requests in the metadata form. |

## Configuring dataset upload

The dataset upload behaviour can be configured under the `upload-dataset` node.
Currently you can:

- Disable the "Full content embargo" option (enabled by default).
- Add a custom message to be displayed in the dataset file deposit section.

The `upload-dataset` node supports the following options:

| Option | Description |
|--------|-------------|
| `allow-full-embargo` | "Full content embargo" is enabled by default. Set this option to 0 to disable it. When users choose to deposit a dataset or software under a "Full content embargo", both the files and the metadata will remain unavailable during the embargo period. |
| `file-deposit/notice` | An HTML message displayed above the file upload area when a depositor edits a dataset. HTML markup, including hyperlinks, is supported. |

How to use:

```xml
<upload-dataset>
  <allow-full-embargo>0</allow-full-embargo>
  <file-deposit>
    <notice>Your message here</notice>
  </file-deposit>
</upload-dataset>
```

## Customizing looks

With the following options, the instance can be branded as necessary.

| Option | Description |
|--------|-------------|
| `site-name` | Name for the instance used in the title of a browser window and as default value in the publisher field for new datasets. |
| `site-description` | Description used as a meta-tag in the HTML output. |
| `site-shorttag` | Used as keyword and as Git remote name. |
| `publisher-rors` | Mapping of publisher names to ROR URLs. Each child is a `<publisher-ror name="..." url="..."/>` element. Used in RO-Crate exports and as the ROR link rendered next to the publisher on the dataset page when the dataset's publisher matches one of the configured names. |
| `support-email-address` | E-mail address used in e-mails sent to users in automated messages. |
| `custom-logo-path` | Path to a PNG image file that will be used as logo on the website. |
| `custom-favicon-path` | Path to an ICO file that will be used as favicon. |
| `small-footer` | HTML that will be used as footer for all pages except for the main page. |
| `large-footer` | HTML that will be used as footer on the main page. |
| `show-portal-summary` | When set to 1, it shows the repository summary of number of datasets, authors, collections, files and bytes on the main page. |
| `show-institutions` | When set to 1, it shows the list of institutions on the main page. |
| `show-science-categories` | When set to 1, it shows the subjects (categories) on the main page. |
| `show-latest-datasets` | When set to 1, it shows the list of latest published datasets on the main page. |
| `colors` | Colors used in the HTML output. See [Customizing colors](#customizing-colors). |

### Customizing colors

The following options can be configured in the `colors` section.

| Option | Description |
|--------|-------------|
| `primary-color` | The main background color to use. |
| `primary-foreground-color` | The main foreground color to use. |
| `primary-color-hover` | Color to use when hovering a link. |
| `primary-color-active` | Color to use when a link is clicked. |
| `privilege-button-color` | The background color of buttons for privileged actions. |
| `footer-background-color` | Color to use in the footer. |
| `background-color` | Background color for the content section. |

## Customizing the menu

The top navigation menu is defined using the `menu` XML element, which can be
placed in a separate menu configuration file and loaded via `include` in the
`djehuty` configuration. The menu supports up to three levels of nesting:
primary menu items, sub-menus, and sub-sub-menus.

### Menu structure

A `menu` element contains one or more `primary-menu` elements, each rendered as
a top-level entry in the navigation bar. Hovering over a primary item reveals
its `sub-menu` children in a dropdown panel. A `sub-menu` may contain
`sub-sub-menu` children.

Every item requires a `title` with its display text. `sub-menu` and
`sub-sub-menu` items also require an `href` element with the destination URL.

| Element | Description |
|---------|-------------|
| `menu` | Root element that groups all primary menu items. |
| `primary-menu` | A top-level navigation bar entry. Requires a `title` child. |
| `sub-menu` | A dropdown item inside a `primary-menu`. Requires `title` and `href` children. May contain one or more `sub-sub-menu` children. |
| `sub-sub-menu` | A flyout item inside a `sub-menu`, displayed to the right on hover. Requires `title` and `href` children. |

### Example

```xml
<djehuty>
  <menu>

    <primary-menu>
      <title>About your Data</title>
      <sub-menu>
        <title>Getting started</title>
        <href>/info/about-your-data/getting-started</href>
      </sub-menu>
      <sub-menu>
        <title>Publish and Cite</title>
        <href>/info/about-your-data/publish-cite</href>
      </sub-menu>
    </primary-menu>

    <primary-menu>
      <title>Collaborations</title>
      <sub-menu>
        <title>Collaborations overview</title>
        <href>https://example.org/collaborations/</href>
      </sub-menu>
      <sub-menu>
        <title>Digital Capacity for NES</title>
        <href>https://example.org/digital-capacity/</href>
        <sub-sub-menu>
          <title>Call 1: Instructors</title>
          <href>https://example.org/digital-capacity/call-1/</href>
        </sub-sub-menu>
        <sub-sub-menu>
          <title>Call 2: Learners</title>
          <href>https://example.org/digital-capacity/call-2/</href>
        </sub-sub-menu>
      </sub-menu>
    </primary-menu>

  </menu>
</djehuty>
```

Keep the menu definition in a dedicated config file and load it from the main
configuration file using `include`:

```xml
<djehuty>
  <include>/etc/djehuty/djehuty-menu.xml</include>
</djehuty>
```

## Configuring privileged users

By default an authenticated user may deposit data. But users can have additional
roles; for example: a dataset reviewer, a technical administrator or a quota
reviewer.

Such additional roles are configured in terms of privileges. The following
privileges can be configured in the `privileges` section:

| Option | Description |
|--------|-------------|
| `may-administer` | Allows access to perform maintenance tasks, view accounts and view reports on restricted and embargoed datasets. |
| `may-run-sparql-queries` | Allows to run arbitrary SPARQL queries on the database. |
| `may-impersonate` | Allows to log in to any account and therefore perform any action as that account. |
| `may-review` | Allows to see which datasets are sent for review, and allows to perform reviews. |
| `may-review-quotas` | Allows access to see requests for storage quota increases and approve or decline them. |
| `may-review-integrity` | Allows access to an API call that provides statistics on the accessibility of files on the filesystem. |
| `may-process-feedback` | Accounts with this privilege will receive e-mails with the information entered into the feedback form by other users. |
| `may-recalculate-statistics` | Views and downloads statistics are not calculated in real time. An administrator with this additional privilege can trigger a recalculation of these statistics, which can be a database-intensive action. |
| `may-receive-email-notifications` | This "privilege" can be used to disable sending any e-mails to an account by setting it to `0`. The default is `1`. |

To enable a privilege for an account, set the value of the desired privilege to
`1`. Privileges are disabled by default, except for
`may-receive-email-notifications` which defaults to `1`.

```xml
<privileges>
  <account email="you@example.com" orcid="0000-0000-0000-0001">
    <may-administer>1</may-administer>
    <may-run-sparql-queries>1</may-run-sparql-queries>
    <may-impersonate>1</may-impersonate>
    <may-review>0</may-review>
    <may-review-quotas>0</may-review-quotas>
    <may-review-integrity>0</may-review-integrity>
    <may-process-feedback>0</may-process-feedback>
    <may-receive-email-notifications>1</may-receive-email-notifications>
  </account>
</privileges>
```

# Running `djehuty`

Before running `djehuty`, consider the [Configuring `djehuty`](#configuring-djehuty)
chapter which provides the configuration options to enable or disable features,
where data will be stored and a way to adapt `djehuty` to your organization's style.

## Running `djehuty`

Invoking `djehuty web` starts the web interface of `djehuty`. On what port it
makes itself available can be configured in its configuration file.

```
djehuty web --config-file=your-djehuty-config.xml
```

## Running `djehuty` behind an `nginx` reverse-proxy

While `djehuty` itself does not support SSL/TLS, it is designed to work together
with a reverse-proxy HTTP server like `nginx`. When `djehuty` starts, it will
bind on a pre-configured address and port, which in turn can be `proxy_pass`ed
to using `nginx`.

The following snippet shows how to configure `nginx`.

```nginx
server {
    listen              443 ssl;
    listen              [::]:443 ssl;
    server_name         example.domain;

    ssl_certificate     /etc/letsencrypt/live/example.domain/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/example.domain/privkey.pem;

    location / {
       # Set 'use-x-forwarded-for' in the djehuty configuration.
       proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
       # The values for address and port depend on what is configured in the
       # djehuty configuration file.
       proxy_pass http://127.0.0.1:8080;
       root /usr/share/nginx/html;
    }
}
```

To ensure `djehuty` receives the actual client IP address so it can log this
information, one can set the `use-x-forwarded-for` option described in
[Essential options](#essential-options).
