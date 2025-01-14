"""This module provides a program-wide configurable state."""

class RuntimeConfiguration:  # pylint: disable=too-few-public-methods
    """This class implements the configurable properties for djehuty."""

    _instance = None
    def __new__ (cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__ (self):

        self.address                     = None
        self.port                        = None
        self.alternative_port            = None
        self.base_url                    = None
        self.log_file                    = None
        self.use_reloader                = None
        self.use_debugger                = None
        self.maximum_workers             = None
        self.transactions_directory      = "."
        self.clear_cache_on_start        = False
        self.storage_locations           = []
        self.storage                     = None
        self.secondary_storage           = None
        self.secondary_storage_quirks    = False
        self.endpoint                    = "http://127.0.0.1:8890/sparql"
        self.update_endpoint             = None
        self.state_graph                 = "https://data.4tu.nl/portal/self-test"
        self.privileges                  = {}
        self.thumbnail_storage           = None
        self.profile_images_storage      = None
        self.iiif_cache_storage          = None
        self.enable_query_audit_log      = False
        self.account_quotas              = {}
        self.group_quotas                = {}
        self.default_quota               = 5000000000
        self.depositing_domains          = []
        self.delay_inserting_log_entries = False
        self.export_directory            = "."
        self.site_name                   = ""
        self.site_description            = ""
        self.site_shorttag               = "4tu"
        self.support_email_address       = ""
        self.allow_crawlers              = False
        self.in_production               = False
        self.in_preproduction            = False
        self.using_uwsgi                 = False
        self.maintenance_mode            = False
        self.sandbox_message_css         = ""
        self.sandbox_message             = False
        self.notice_message              = False
        self.show_portal_summary         = True
        self.show_institutions           = True
        self.show_science_categories     = True
        self.show_latest_datasets        = True
        self.disable_2fa                 = False
        self.enable_iiif                 = False
        self.disable_collaboration       = False
        self.automatic_login_email       = None
        self.handle_certificate_path     = None
        self.handle_certificate          = None
        self.handle_private_key_path     = None
        self.handle_private_key          = None
        self.handle_url                  = None
        self.handle_prefix               = None
        self.handle_index                = None
        self.small_footer                = (
            '<div id="footer-wrapper2"><p>This repository is powered by '
            '<a href="https://github.com/4TUResearchData/djehuty">djehuty</a> '
            'built for <a href="https://data.4tu.nl">4TU.ResearchData</a>.'
            '</p></div>'
        )
        self.large_footer                = self.small_footer
        self.orcid_client_id             = None
        self.orcid_client_secret         = None
        self.orcid_endpoint              = None
        self.orcid_read_public_token     = None
        self.identity_provider           = None
        self.saml_config_path            = None
        self.saml_config                 = None
        self.saml_attribute_email        = "urn:mace:dir:attribute-def:mail"
        self.saml_attribute_first_name   = "urn:mace:dir:attribute-def:givenName"
        self.saml_attribute_last_name    = "urn:mace:dir:attribute-def:sn"
        self.saml_attribute_common_name  = "urn:mace:dir:attribute-def:cn"
        self.saml_attribute_groups       = None
        self.saml_attribute_group_prefix = None
        self.sram_organization_api_token = None
        self.sram_collaboration_id       = None
        self.datacite_url                = None
        self.datacite_id                 = None
        self.datacite_password           = None
        self.datacite_prefix             = None
        self.ssi_psk                     = None
        self.menu                        = []
        self.colors                      = {
            "primary-color":            "#f49120",
            "primary-color-hover":      "#d26000",
            "primary-color-active":     "#9d4800",
            "primary-foreground-color": "#000000",
            "privilege-button-color":   "#fce3bf",
            "footer-background-color":  "#707070"
        }

config = RuntimeConfiguration()
