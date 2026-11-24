# djehuty Roadmap

This roadmap gives a high-level overview of recent and upcoming developments for the 4TU.ResearchData platform and related open-source infrastructure.

> **Note:** This roadmap describes direction, not commitments or delivery dates.
> Items may change based on community feedback, resources and technical findings.
>
> Last updated: **November 2026** · Next review: February 2027


## Priorities

Our goal is to provide leading domain-specific infrastructure for research data and software. Each item under *Completed*, *In progress* and *Exploring* is tagged:

- **Open and community-driven:** enabling community contribution through open source software
- **Federation and partners:** strengthening cooperation between 4TU.Federation partner institutions to build a federated ecosystem for data and software
- **Interoperability:** connecting with other research data infrastructure
- **Reliable and sustainable:** improving the scalability, reliability, and maintainability of the platform to support long-term operation and growth.


## Completed in 2026
The following work was completed during 2026 and contributes to the priorities outlined above.


### Open source governance and practices (Q1-Q2 2026)
*Theme: Open and community-driven*

To enable community contributions and increase transparency around project development, we adopted a number of established open source governance and collaboration practices:
Migrated the development workflow to GitHub, including issue tracking, project planning, and pull request reviews.
Published a governance model, contribution guidelines, and a Code of Conduct to clarify how decisions are made and how community members can contribute.
Introduced GitHub Security Advisories to provide a responsible and transparent process for reporting and managing security vulnerabilities.


### Rebranding with the new 4TU.ResearchData identity (Q3 2026)
*Theme: Federation and partners*

We aligned the repository website with the new 4TU.ResearchData identity, providing a consistent visual experience across services and communication channels.


### Physical sample support: IGSN (Q3 2026)
*Themes: Federation and partners, Interoperability*

Researchers can register persistent identifiers (IGSNs) for physical samples and link them to datasets, software and publications.


### Easier deployment and self-hosting (Q3 2026)
*Themes: Open and community-driven, Reliable and sustainable*

We added Helm charts and Kubernetes support, and greatly simplified the setup so running your own instance now only requires `just`, `uv` and Docker. Instances can now also load custom
stylesheets and assets, so you can apply your own branding more easily.


### Documentation (Q3 2026)
*Theme: Open and community-driven*

We rewrote the LaTeX documentation in MkDocs and published OpenAPI documentation for the API, so developers and integrators can find and use it more easily.


### Code quality and developer experience (Q3 2026)
*Theme: Open and community-driven*

We introduced linting to keep the codebase consistent and make contributions easier to review.


### Community spaces (Q4 2026)
*Theme: Open and community-driven*

We opened the [community website](https://djehuty.4tu.nl/community/), launched [GitHub Discussions](https://github.com/4TUResearchData/djehuty/discussions)
for questions and ideas, and started the monthly [Community Hour](https://djehuty.4tu.nl/community/community-hour/), an open online meeting for updates and discussion.


## In progress

### Persistent identifier expansion
*Theme: Interoperability*

Adding support for further identifiers: ROR (organisations), RAiD (research projects), Funder ID, and identifiers for research instruments.


### Statistics and reporting
*Theme: Federation and partners*

Reworking the current implementation, including the API, to provide reliable statistics on use and access of the repository, and publishing a quarterly report on the web for partner institutions and the public.


### Improving the deposit and publication process
*Theme: Federation and partners*

Working with data curators to identify where the process can be improved for depositors and repository staff.

For example, administrators can now change the embargo date and licence of published datasets, remove files from a published version, and merge user accounts.


### Modernising the platform architecture
*Themes: Open and community-driven, Reliable and sustainable:*

Improving the underlying architecture of djehuty to make it more scalable, reliable, and easier to operate. This includes the gradual migration to modern technologies such as FastAPI, support for shared caching with Valkey, resumable large-file downloads, storage maintenance mode, database migrations, cloud-friendly JSON configuration, and operational improvements such as log rotation.


## Exploring

These are under investigation; we have not committed to them.


### Aligning the community website and the repository
*Theme: Open and community-driven*

Looking at a more consistent experience across both, for example shared login and author profiles.


### Harvesting API for PURE
*Theme: Interoperability*

Exploring a harvesting interface so institutions using PURE can reuse repository metadata.


### Community communication
*Theme: Open and community-driven*

Exploring options for how the community communicates and collaborates.


## Operational activities

- Maintaining and securing the platform, including regular updates.
- Improving code quality and consistency across the codebase.
- Supporting depositors and partner institutions, and curating published data.
- Reviewing community contributions and ideas.


## Get involved

We welcome ideas and contributions from researchers, developers, data stewards and infrastructure providers.

- Missing an integration with a tool from your domain? Suggest it in our [Ideas category in GitHub Discussions](https://github.com/4TUResearchData/djehuty/discussions/categories/ideas)
- Join the [monthly Community Hour](https://djehuty.4tu.nl/community/community-hour/)
- Contribute: [CONTRIBUTING.md](https://github.com/4TUResearchData/djehuty?tab=contributing-ov-file) · [GOVERNANCE.md](https://github.com/4TUResearchData/djehuty/blob/main/GOVERNANCE.md) · [CODE_OF_CONDUCT.md](https://github.com/4TUResearchData/djehuty?tab=coc-ov-file)

