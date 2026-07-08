# Changelog

All notable changes to djehuty are documented in this file. Newest releases
appear first; this file is the source of truth for release notes. The LaTeX
news section (`doc/news.tex`) is regenerated at release time by `just news`.

Commit links point to <https://github.com/4TUResearchData/djehuty>.

## [v26.3.2]

This patch release includes 5 commits focused on security, maintenance and dependencies.

### Incremental improvements

- Create a support for database migrations. ([dee251c](https://github.com/4TUResearchData/djehuty/commit/dee251c20c9e9e27fbbb76e526fecddbc9758646))
- Update Python dependencies for security and performance. ([70fbb8b](https://github.com/4TUResearchData/djehuty/commit/70fbb8be809571c62626bb65a716a720b2e84386),
[11ce5e8](https://github.com/4TUResearchData/djehuty/commit/11ce5e8cf1e49b97bbfb8f8baf93fe93ff29deca))

### Bugfixes

- Restrict search order to an allow-list. ([897c915](https://github.com/4TUResearchData/djehuty/commit/897c9159334ccbde530ba19bbcfaad09a21d3f53))
- Escape the session name field before templating. ([f9f3e47](https://github.com/4TUResearchData/djehuty/commit/f9f3e470d0fcf74ff6bf1a67c0451078f14d2862))

## [v26.3.1]

This patch release includes 12 commits focused on maintenance and bug fixes.
It updates multiple Python, Docker, and GitHub Actions dependencies, improves
the image build process, deprecates Python 3.9 support, and fixes an issue that
could generate duplicate groups in the database.

### Incremental improvements

- Deprecate Python 3.9 support. ([6b25918](https://github.com/4TUResearchData/djehuty/commit/6b25918bb9112bd3f69c5bec3f74ad8c0399decd))
- Make the production Docker image build the same way as the development image.
([b651c96](https://github.com/4TUResearchData/djehuty/commit/b651c969d1226cad6e6d1c8d2c878dae3a69b048))
- Update the Docker base image to the latest patched python version.([60ce009](https://github.com/4TUResearchData/djehuty/commit/60ce009cb8468b53c6922e91a789aabca9ac8221))
- Update GitHub Actions dependencies.([4995863](https://github.com/4TUResearchData/djehuty/commit/4995863f654cafc5d9c282b36b21272e80248eac),
[0aef7c8](https://github.com/4TUResearchData/djehuty/commit/0aef7c8bab2154d56c71bcf35b890290087f7436))
- Update Python dependencies for security and performance. ([bc89ceb](https://github.com/4TUResearchData/djehuty/commit/bc89cebc71c0db10a27c253122b52cf9b618c097),
[64a0ef5](https://github.com/4TUResearchData/djehuty/commit/64a0ef52a1777cb8cd174318810e9e7364cdeda0),
[ee4ef99](https://github.com/4TUResearchData/djehuty/commit/ee4ef99c4fc5989f827e937268871a44e911e3be),
[b30a44c](https://github.com/4TUResearchData/djehuty/commit/b30a44c6dd22941e480fb32ee69aa88414c0dbbe))

### Bugfixes

- Fix an issue where `start` could generate duplicate groups in the database. ([2ffafde](https://github.com/4TUResearchData/djehuty/commit/2ffafde812ec8653275c530437aa05c597e00e5a))

## [v26.3]

The third release of 2026 consists of 21 commits made by 3 authors.

We’ve kicked off a new phase of improvements focused on reliability, usability, 
and long-term sustainability. This release expand automated testing and automated 
process and quality assurance efforts, helping make Djehuty more robust, efficient, 
and easier to evolve for both users and developers.

### New features

- Add JSON as a supported Djehuty config format alongside XML to support future cloud-native deployments. ([6ace7fe](https://github.com/4TUResearchData/djehuty/commit/6ace7fe252325c517682fd4e0f7bf88d5e6ed21b))
- Add dashboard for administrative changes in published datasets allowing embargo dates updates. ([e14c93d](https://github.com/4TUResearchData/djehuty/commit/e14c93d8b42562fe6d5a6e7e81d0a05af1f6b8d1))
- Add dashboard for administrative changes in published datasets allowing licenses updates. ([34a9909](https://github.com/4TUResearchData/djehuty/commit/34a9909e6c4d7d71e17555a7ec4b24628e52d0e7))
- Add ROR link to the landing page of the publications. ([68aa989](https://github.com/4TUResearchData/djehuty/commit/68aa9891108523ba806b2e6c2f7f7475d67bd233))

### Incremental improvements

- Add E2E testing setup using Playwright. ([0f587a2](https://github.com/4TUResearchData/djehuty/commit/0f587a2da459b1db210d9c6c33d4ee00eb6a2df3)
- Add code coverage using codecov. ([d50761a](https://github.com/4TUResearchData/djehuty/commit/d50761adbf6d3293bc387c5888bb68aaa659ec2a))
- Add container image and python build workflow for automate release and test process. ([75cad1e](https://github.com/4TUResearchData/djehuty/commit/75cad1e8b194c8c45c207a3768c94e737f2c55e8))
- Add process to do easy restore of the database for the development environment. ([c66cb30](https://github.com/4TUResearchData/djehuty/commit/c66cb30ae99ee7120da7bfd8bb3f9f36c092519d))
- Add configuration to support sub-submenus in the layout. ([d54d2d5](https://github.com/4TUResearchData/djehuty/commit/d54d2d56f98cf41ab8b3b7fc89dfab5c4d19a2bd))
- Add image support for non-font awesome icons. ([7e8e0b0](https://github.com/4TUResearchData/djehuty/commit/7e8e0b078d600c13b90697f7e452988b06ae45ba))
- Update python dependencies for security and performance. ([2ec35fd](https://github.com/4TUResearchData/djehuty/commit/2ec35fd17c3ac525c8f48eef370d994a785e2e09))

### Bugfixes

- Implement S3 factory for reusable clients to lower memory footprint. ([4dbc4ca](https://github.com/4TUResearchData/djehuty/commit/4dbc4cac1f9cc90bdc8546f41d2065fb98b046e1))

### Documentation

- Documents the full release process and add a CHANGELOG.md file as single source of historical changes. ([58f075e](https://github.com/4TUResearchData/djehuty/commit/58f075e03329a3e769e9d1b1fdf9b31a2039600e))

## [v26.2]

The second release of 2026 consists of 9 commits made by 2 authors.

### Documentation

- Add SECURITY.md with coordinated disclosure policy. ([9076560](https://github.com/4TUResearchData/djehuty/commit/9076560f16f1b18c20120d5093d60b271f357f18))
- Update GOVERNANCE.md Diagram as a code. ([f1108ed](https://github.com/4TUResearchData/djehuty/commit/f1108ed8dce7b03c6ea57347c3e962605afab3c7))

### Bugfixes

- Fix documentation build issues and make debugging it easier. ([d0f3f95](https://github.com/4TUResearchData/djehuty/commit/d0f3f957561fc51fa2e2854d404bbceaecef42a3))
- Fix new author fields not displaying in collections. ([60ec8bf](https://github.com/4TUResearchData/djehuty/commit/60ec8bf4c35e03e1f4cf0c59f0c491fe68cd9691))

### Incremental improvements

- Add option to disable “Full content embargo”. ([42b6eb1](https://github.com/4TUResearchData/djehuty/commit/42b6eb1a9991da9288bfc12571d91606b004d1f9))
- Add custom message to dataset file deposit. ([5f42855](https://github.com/4TUResearchData/djehuty/commit/5f42855a88cf86dbb21c5c111504fda95a2e3f69))
- Make primary menu layout dynamic and flexible. ([0f3f8d9](https://github.com/4TUResearchData/djehuty/commit/0f3f8d9b95dc2e0ae96fc5b5088af8dd6a8c5c52))
- Implement easy development start process with djehuty. ([c8635b4](https://github.com/4TUResearchData/djehuty/commit/c8635b4c7bc9ca53cbb4efe0d16e3e8e763a7652))
- Create dependabot.yml file to monitors dependencies. ([fdbeee7](https://github.com/4TUResearchData/djehuty/commit/fdbeee753a57d31664a4fb8f7a1bd830bdc5084c))

## [v26.1]

The first release of 2026 consists of 10 commits made by 4 authors.

### New features

- Introduce CODECHECK request in metadata form. ([c61eed8](https://github.com/4TUResearchData/djehuty/commit/c61eed80e18ff9f89d4030ca91ad5a314e799c6f), [f6143dd](https://github.com/4TUResearchData/djehuty/commit/f6143dd18514bf8012ff967087cf0e656726de2e))

### Documentation

- Add contributing guidelines, code of conduct, and governance document. ([4e66a99](https://github.com/4TUResearchData/djehuty/commit/4e66a99611189d2832a4c9754075986aace1bb39), [afd028d](https://github.com/4TUResearchData/djehuty/commit/afd028d081c1192ecfe7f03a610ae9005aeb7785), [7b10467](https://github.com/4TUResearchData/djehuty/commit/7b10467a462975ccc0145658e3d6269f41aa2fdb))
- Update contact information and copyright license. ([4c5de37](https://github.com/4TUResearchData/djehuty/commit/4c5de37067420fa11851351ea20060cfbb100a15), [53bf4e0](https://github.com/4TUResearchData/djehuty/commit/53bf4e0b4ec5c45746ea63f6922285d4e30b21f0))
- Add issue and pull request templates. ([568f94d](https://github.com/4TUResearchData/djehuty/commit/568f94d3c1a212304e520a93a5935f7eba43b340))

### Bugfixes

- Fix rendering of DOI in private viewing. ([d93ff4b](https://github.com/4TUResearchData/djehuty/commit/d93ff4b3195f129e2dff2d7641c8cb7f71e19602))

### Incremental improvements

- Add support for symbolic links in generated zip files. ([2bc0e4e](https://github.com/4TUResearchData/djehuty/commit/2bc0e4e27bff8f0dee00634aeb33f9328b7da0cf))

## [v25.6]

The June release of 2025 consists of 15 commits made by 3 authors.

### New features

- Add initial support to display a CodeWorks badge. ([4b3d521](https://github.com/4TUResearchData/djehuty/commit/4b3d5212b5bd0d26cd6e928b9bf9c9e23a4e4439))
- Add auto-completion support for keywords. ([0324453](https://github.com/4TUResearchData/djehuty/commit/032445341f6a066ba15cd37579dfd866ed4948a4))

### Bugfixes

- Return empty list upon error in `/v3/datasets/<uuid>.git/contributors`. ([5a7c70c](https://github.com/4TUResearchData/djehuty/commit/5a7c70c0662f4cd2c7b3fc2a67a771e311c6512d))
- Avoid duplicating entries in the funding autocompletion. ([a538873](https://github.com/4TUResearchData/djehuty/commit/a53887390a9bee48a2ba3bf9d76f050e4e285c49))

### Incremental improvements

- Improve documentation. ([3458987](https://github.com/4TUResearchData/djehuty/commit/3458987dbb65b284334d6303615a4ef5c1c546db), [9edb43e](https://github.com/4TUResearchData/djehuty/commit/9edb43e9c09024c1195ae5cd2a4deedc837daf3e), [f15e95f](https://github.com/4TUResearchData/djehuty/commit/f15e95f9dad16a3369db42e90f04c65edb946771))
- Improve the caching system. ([4b1c054](https://github.com/4TUResearchData/djehuty/commit/4b1c054f7dd7dd564f4de12d1bd114852b1e288b), [4cee56a](https://github.com/4TUResearchData/djehuty/commit/4cee56a6fd01226f4982c5b9378180fc7a8fd5ca))
- Introduce permission to recalculate statistics. ([5c6beab](https://github.com/4TUResearchData/djehuty/commit/5c6beab7792da231c53c180c8b0be33eebdc5620))
- Improve contrast of the "connect with ORCID" button. ([c1b4d1b](https://github.com/4TUResearchData/djehuty/commit/c1b4d1bfcc3d1074d2137119b53c7766f2fe3d2f))

## [v25.5]

The May release of 2025 consists of 14 commits made by 3 authors. This release contains a security fix for a SPARQL injection found by Thomas Thelen and a a security fix for a HTML injection found by Anass Ksiber. Many thanks to both for reporting and assisting in resolving these vulnerabilities.

### UI revisions

- Introduce an "Interoperability" section with links to the RO-Crate metadata API and the IIIF manifest. ([2a49687](https://github.com/4TUResearchData/djehuty/commit/2a49687d0fab911f52b461f806dd7eadcc15df30))

### Security

- Properly escape session cookie value. ([da1cbf2](https://github.com/4TUResearchData/djehuty/commit/da1cbf2b15155ce4541ab7ca81f3102067fb749f))
- Avoid possibility of HTML injection in the search page. ([4f479f6](https://github.com/4TUResearchData/djehuty/commit/4f479f6869a2b7eeaf7cd78832419014eddf06f8))

### Bugfixes

- Avoid re-creating the Handle configuration. ([80f1f2e](https://github.com/4TUResearchData/djehuty/commit/80f1f2e3e06b2b85cede6b17e75793bb0ab2d670))
- Ensure the v2 API respects the depositing-domains property. ([45941d2](https://github.com/4TUResearchData/djehuty/commit/45941d2d9217ff2c389a0072002249dac64c5645))
- Don't show file metadata for restricted datasets in RO-Crate output. ([b81c730](https://github.com/4TUResearchData/djehuty/commit/b81c730ec7d36e88f3cb4461c2920c5ec2d79f6c))
- Improve render quality of PDF files in the IIIF Image API. ([6556bf2](https://github.com/4TUResearchData/djehuty/commit/6556bf2ff6d7dd57ea8630199e7738dfbd49686f), [ffb3596](https://github.com/4TUResearchData/djehuty/commit/ffb35961a7bc24477913ca428c44001543342e8a))
- Document acceptable parameters for various API endpoints. ([b5dea01](https://github.com/4TUResearchData/djehuty/commit/b5dea019bcaaa1e3beae643ab8ed4c8776e0e532))
- Distribute missing files in the release tarball. ([76b2951](https://github.com/4TUResearchData/djehuty/commit/76b29514e469a28ad3bfc080a2711672aa0f3765))

### Technical debt

- Simplify the `dist-docker` target. ([7b08aae](https://github.com/4TUResearchData/djehuty/commit/7b08aae0f3c44447869d7dab53bbb65678ce3747))

## [v25.4]

The April release of 2025 consists of 51 commits made by 4 authors.

### New features

- Implement IIIF Presentation API. ([1eb35f4](https://github.com/4TUResearchData/djehuty/commit/1eb35f4f424e379462a34a9f032a14d74892d052), [b052e5d](https://github.com/4TUResearchData/djehuty/commit/b052e5dc7a0a469a5f49d3d6d035fe45f37b4dc5), [9dca2ff](https://github.com/4TUResearchData/djehuty/commit/9dca2ffa5dfec843bfde15a3c61eacdfd3d38ecb), [68f2bba](https://github.com/4TUResearchData/djehuty/commit/68f2bbacd960aae7a7bbb185562033c78dc191d2), [ed0a39e](https://github.com/4TUResearchData/djehuty/commit/ed0a39e19ea25709cb577ecfb7f41e4d4e004433), [8f97591](https://github.com/4TUResearchData/djehuty/commit/8f975910f69b9e4f484eefaf59e02e7a9b5ca527), [ce43c45](https://github.com/4TUResearchData/djehuty/commit/ce43c4590a3668e10bc0826cd5925169d235cc7f), [a4b43cd](https://github.com/4TUResearchData/djehuty/commit/a4b43cdd778402ad890b48ad42b77f2965d377cc))
- Implement tiles property for IIIF Image API. ([e9453e1](https://github.com/4TUResearchData/djehuty/commit/e9453e1ec43514a2fc1a7a6256ee17203f38a82a))
- Implement `static-resources-cache` option. ([1529d96](https://github.com/4TUResearchData/djehuty/commit/1529d961aa833fb388809ebb02c6e2d0455411d4))

### Security

- Harden the `Content-Security-Policy` as an extra layer of defence against cross-site scripting. ([3c2c532](https://github.com/4TUResearchData/djehuty/commit/3c2c5329089a41d2f4637fed9c0c1de19c5669ef), [ce428d8](https://github.com/4TUResearchData/djehuty/commit/ce428d824c0f7e30a85054970f62fa0734011d26), [4a1abf6](https://github.com/4TUResearchData/djehuty/commit/4a1abf60e94e07ff6db748c447dc1ed1508a33a5), [da39ace](https://github.com/4TUResearchData/djehuty/commit/da39ace8eec25d3a4646b288c2d9156022fd7063), [1bcc4f9](https://github.com/4TUResearchData/djehuty/commit/1bcc4f92dbda97bd38328c2f00c843996d3c9418), [13c06ef](https://github.com/4TUResearchData/djehuty/commit/13c06ef7bd5465adeda52e8fff9fe8d0620547c1), [b5434f9](https://github.com/4TUResearchData/djehuty/commit/b5434f969275314f4180f28fcf88de1bf1b79c3b), [7a15707](https://github.com/4TUResearchData/djehuty/commit/7a157070a9ffcf62e5d0426dbc21ee405248a274), [9d84583](https://github.com/4TUResearchData/djehuty/commit/9d84583c80ec001f461bf113bfc52c5045bb3c39))

### Bugfixes

- Ensure ZIP files of Git repositories are bit-reproducible. ([586c304](https://github.com/4TUResearchData/djehuty/commit/586c3045883c2b13ebec1c6a7aa88f740b39f40e))
- Fix alignment of search results when viewed as a list. ([2463ebb](https://github.com/4TUResearchData/djehuty/commit/2463ebbcff89e8ddb18c06925b2dcfa6520af938))
- Document the institution API endpoints. ([fc27ddf](https://github.com/4TUResearchData/djehuty/commit/fc27ddf7ab963c964d7ebcbb2e2803f780de19e7))
- Show reviews for institutional reviewers based on the group rather than accounts. ([6ef0eca](https://github.com/4TUResearchData/djehuty/commit/6ef0eca6c4c498c651e25e3f178dd1dec9e1c91e))

### Technical debt

- Code clean-ups. ([02ce6b3](https://github.com/4TUResearchData/djehuty/commit/02ce6b383d2f83cbdb04daaa212f27f4dd0633ba), [a1e7c2f](https://github.com/4TUResearchData/djehuty/commit/a1e7c2fe62c0011a214fc7e7edb999ffade3463a), [1a3adcf](https://github.com/4TUResearchData/djehuty/commit/1a3adcfccc8f309d17815f00a51559bf75a9412a), [c61f272](https://github.com/4TUResearchData/djehuty/commit/c61f2724723965f4783a1af7ae86e3218e7bcce0), [9d6307a](https://github.com/4TUResearchData/djehuty/commit/9d6307afa163954ad496007306f65c921ea6773e), [a4e5b38](https://github.com/4TUResearchData/djehuty/commit/a4e5b38a75a019d09b6175a3fc485c16496a4c31), [e60e6f3](https://github.com/4TUResearchData/djehuty/commit/e60e6f3734bc8ec8d32b8d92d0fd375a57aa44e9), [51817a2](https://github.com/4TUResearchData/djehuty/commit/51817a2b540adb44bd1b1db8d17b90b3f20f529b), [96d3382](https://github.com/4TUResearchData/djehuty/commit/96d338254309ae683935fe9d423a59c0cc39cecd), [2de1e41](https://github.com/4TUResearchData/djehuty/commit/2de1e417fbc658b79e1f3ba6fb1406fc7cc7c044), [35afe28](https://github.com/4TUResearchData/djehuty/commit/35afe28e959f3275489223f028d8d33f2e91e2da))

## [v25.3]

The March release of 2025 consists of 57 commits made by 2 authors. This release contains various bugfixes, minor UI revisions, minor feature updates, and contains the foundation for an extra security layer to prevent cross-site scripting vulnerabilities. The release date slipped a couple of days because yours truly wanted to give last-minute changes a little bit of time to make sure no regressions occurred before formalizing the release.

### New features

- Implement API endpoints for reviewers. ([1de7f68](https://github.com/4TUResearchData/djehuty/commit/1de7f680840ec882752de1fe53004a4bed16f568), [038e931](https://github.com/4TUResearchData/djehuty/commit/038e931b96eeabb72d4f0c305c0dc0ee2afab696), [2f59635](https://github.com/4TUResearchData/djehuty/commit/2f5963553910929ef479eadeb1c770780fd8df93))
- Report number of search results in the `/v2/articles/search` endpoint. ([a8917a8](https://github.com/4TUResearchData/djehuty/commit/a8917a837e9d5d70a618ff50fd29bb7cc959febd))
- Add `SoftwareSourceCode` to RO-Crate output. ([79cf0b3](https://github.com/4TUResearchData/djehuty/commit/79cf0b32ada27780ef0efadc0d20556c8717eb84))

### UI revisions

- Revise the "Cite" and "Collect" buttons on landing pages. ([b0b9dbd](https://github.com/4TUResearchData/djehuty/commit/b0b9dbd1f21e1aec464985daff7c5af100bc5346))
- Remove the need for a "save URL" button in the dataset metadata form. ([a853085](https://github.com/4TUResearchData/djehuty/commit/a853085c98417bcfe8b50d0e41e56a61ef31456e))
- Revise the versions drop-down menu on landing pages. ([e5b89ce](https://github.com/4TUResearchData/djehuty/commit/e5b89ce23eec6e1284a22db4802d05e459f29454))
- Fix tile scaling on the main page for different zoom levels. ([7a30bfa](https://github.com/4TUResearchData/djehuty/commit/7a30bfa47ef1c3977180dcc4b0ec31f7ff06e89a))

### Security

- Addressed a Cross-Site-Scripting vulnerability in the search functionality. ([40b12a5](https://github.com/4TUResearchData/djehuty/commit/40b12a5597407a3d67eec5a5cb570d0725197d92))
- Only display e-mail address of authors to the creators of such records. ([05a56fa](https://github.com/4TUResearchData/djehuty/commit/05a56fa18367da28e2366a90e92a43af4639dc5f))

### Bugfixes

- Fix author ordering for collections. ([244017a](https://github.com/4TUResearchData/djehuty/commit/244017a014a4b4d36c8b4d21709996fdf24af635))
- Fix bug in cached responses in the IIIF Image API implementation. ([88d68c7](https://github.com/4TUResearchData/djehuty/commit/88d68c78783a654864e4264c6b60a01793d58e44))
- Fix bug with proportional scaling in the IIIF Image API implementation. ([05d5c7a](https://github.com/4TUResearchData/djehuty/commit/05d5c7a8550e63c395a75c73b873b1b70c08bedd))
- Fix various bugs with rendering HTML entities and tags. ([d3667ed](https://github.com/4TUResearchData/djehuty/commit/d3667ed8bcee0028ceee945351af1182d67d3e99), [3b19d7d](https://github.com/4TUResearchData/djehuty/commit/3b19d7de8c647be71708252c6de123a93fecc327), [08e4fc7](https://github.com/4TUResearchData/djehuty/commit/08e4fc77a90b780b491ca9aa701fa758b43f4a5a), [3a1f3dd](https://github.com/4TUResearchData/djehuty/commit/3a1f3dde5e0e72518c2860afeda8c45eca112e6f))
- Avoid a divide-by-zero situation with quota usage calculation. ([cefde15](https://github.com/4TUResearchData/djehuty/commit/cefde15ddb393507004e7f69d8c2658650a88fa2))
- Fix creating datasets with repeated fields using the v2 API. ([74fe025](https://github.com/4TUResearchData/djehuty/commit/74fe025dbc8b6369920ee7a5fe2f3cea35b2e358), [87127c1](https://github.com/4TUResearchData/djehuty/commit/87127c1f818110d68644e668388f1c61535f5525))
- Fix setting default fields when creating a dataset using the API. ([7f18338](https://github.com/4TUResearchData/djehuty/commit/7f183389d608121c46cd168cbe40681b72789f71))
- Fix returning Git statistics for empty Git repositories. ([be3630a](https://github.com/4TUResearchData/djehuty/commit/be3630a63cfc3f933be9b130b0825602d5898e98), [2cffe95](https://github.com/4TUResearchData/djehuty/commit/2cffe955a2f4a95afb56cb41016559fbce8bbc53), [c3227a7](https://github.com/4TUResearchData/djehuty/commit/c3227a768dd1cd476105f8a86e1de3a752af336f))

### Technical debt

- Work towards a stricter Content-Security-Policy by avoiding inline use of `style` attributes, `script` elements, and event handlers. ([b862fdf](https://github.com/4TUResearchData/djehuty/commit/b862fdf3d558e9ef030f36ce34d2564999fd94c6), [18b3bbe](https://github.com/4TUResearchData/djehuty/commit/18b3bbe3e721f0154365fb0ed1252620b516fe8d), [f08542e](https://github.com/4TUResearchData/djehuty/commit/f08542ecb8f554950bd8387b01b16640cfc70935), [1c248a1](https://github.com/4TUResearchData/djehuty/commit/1c248a1e238b0fc4bce3766fb7a196d631beec95), [99cf348](https://github.com/4TUResearchData/djehuty/commit/99cf348f833b2180425778f900d280d83706dee1), [7524bbb](https://github.com/4TUResearchData/djehuty/commit/7524bbbd26f4ecee67165d44437b2ad41f1d5919), [4d66963](https://github.com/4TUResearchData/djehuty/commit/4d6696335e3fb8a2e01d4b3b5d9176b70c8190be))
- Avoid hard-coded versions in the documentation for the RPM download links. ([21be87d](https://github.com/4TUResearchData/djehuty/commit/21be87dc0efdf5615eefe339ee1ae9c67df6e0c2))
- Avoid repetitive text in the documentation by using macros. ([088f8a1](https://github.com/4TUResearchData/djehuty/commit/088f8a13cf79b47adb731b3d24c672695198c863), [f3dc9c8](https://github.com/4TUResearchData/djehuty/commit/f3dc9c8cd6a84af0c830fcc905d73eaef03828bc))
- Build Docker images with C development libraries to work around "xmlsec" build issues. ([2c03cb3](https://github.com/4TUResearchData/djehuty/commit/2c03cb3cb02bfc85279986f7508291349bf5c609))

## [v25.2]

The February release of 2025 consists of 75 commits made by 2 authors. The major new features in this release are initial support for RO-Crate and direct support for S3 buckets. The release was delayed to include an important security fix for a Cross-Site-Scripting vulnerability found by Aaron Liebig. Many thanks for reporting and assisting in resolving this vulnerability.

### New features

- Implement initial support for RO-Crates. ([5ffee87](https://github.com/4TUResearchData/djehuty/commit/5ffee87a7b9cfefacea984deb4c78f5007581e8e), [96ee261](https://github.com/4TUResearchData/djehuty/commit/96ee261fff36d08e7a2bd2f882a7a7e98d434c75))
- Implement support for S3 buckets via `boto3`. ([1077e25](https://github.com/4TUResearchData/djehuty/commit/1077e2503c1e9e338849c5dee250a1e6483137b4), [67fe48d](https://github.com/4TUResearchData/djehuty/commit/67fe48dbc538d2f00bf687504451e60611021287), [2e5394b](https://github.com/4TUResearchData/djehuty/commit/2e5394b417518efbff5accbbe06f65cf7ba896cb), [09e20e4](https://github.com/4TUResearchData/djehuty/commit/09e20e40551404e0957f1fd2f742ffa156442294), [30209a7](https://github.com/4TUResearchData/djehuty/commit/30209a7544a35d2da700e8f02d86f30bcb651082), [7e6d147](https://github.com/4TUResearchData/djehuty/commit/7e6d147fce19329126c91f2a056070d54e1b093f))
- Implement ability to extract/replay log entries. ([a5a2c09](https://github.com/4TUResearchData/djehuty/commit/a5a2c090389776346944b47554c129f4e686f97e))

### Security

- Addressed a Cross-Site-Scripting vulnerability. ([38e89a0](https://github.com/4TUResearchData/djehuty/commit/38e89a0c8ef351bdb524ff8bcb30b44b3ba8d04f))

### Bugfixes

- Improve rendering for accessibility. ([a3e456c](https://github.com/4TUResearchData/djehuty/commit/a3e456cf172c52b41b071133d9d71883e606c786), [7cb7654](https://github.com/4TUResearchData/djehuty/commit/7cb7654fcb751cd303bf447abde95a7b57f36d7c), [11bba95](https://github.com/4TUResearchData/djehuty/commit/11bba959809595d1fc233be6ddd3cba4575a97fc), [c74ef45](https://github.com/4TUResearchData/djehuty/commit/c74ef45f1523a4e0a4905021a31996a40e4ced97))
- Apply user interface updates. ([b2c213a](https://github.com/4TUResearchData/djehuty/commit/b2c213ac9db2d306c8c874c0c8d60367414ba33b), [3f13e0c](https://github.com/4TUResearchData/djehuty/commit/3f13e0c7592125911e9d1dfe442c13c80f2e8c1b), [98606df](https://github.com/4TUResearchData/djehuty/commit/98606dfcc2e8ddf5d8574f7476b13dd688c314cf), [858f7b7](https://github.com/4TUResearchData/djehuty/commit/858f7b7aa5dca16bf3a1043e581f16b42951a569), [d4db446](https://github.com/4TUResearchData/djehuty/commit/d4db446034d81d9961ea2e4d888a1d685dbde2ab), [c327f19](https://github.com/4TUResearchData/djehuty/commit/c327f196f6f2eed3cbbad4d1f3c2136a3cb5898c), [2210705](https://github.com/4TUResearchData/djehuty/commit/22107051ea5a31a8c3e5488f59936baee782b7a1), [c87550c](https://github.com/4TUResearchData/djehuty/commit/c87550cc5a176c0d9b706f6da6ee8de2c907a83d), [6642dcf](https://github.com/4TUResearchData/djehuty/commit/6642dcf94bd118659cd0541485dbc032b3497561))
- Enhance the documentation. ([57192bb](https://github.com/4TUResearchData/djehuty/commit/57192bbb83aec6512dbcbdf4c26203ebe18fe099), [3a864f0](https://github.com/4TUResearchData/djehuty/commit/3a864f07a09e9d16997208b5cb32b6aedc7c18e4), [be65be3](https://github.com/4TUResearchData/djehuty/commit/be65be335b4807bedbc89f6b1ed5683969001a3a), [ea4e623](https://github.com/4TUResearchData/djehuty/commit/ea4e623dbe2dd66091595cdb551cb6a32e175c75), [1c6267e](https://github.com/4TUResearchData/djehuty/commit/1c6267ec4e4c21c66344b3ad1481049743542259), [8d4d812](https://github.com/4TUResearchData/djehuty/commit/8d4d81266a2efc210d74bbe5e923821fb9cd278d))
- Show precise error messages when input validation fails in the edit-dataset and edit-collection forms. ([bfd2110](https://github.com/4TUResearchData/djehuty/commit/bfd2110f7a5de061cc9921ef4c184be433fbbab3))

### Technical debt

- Remove `urllib3` as explicit dependency. ([672eaff](https://github.com/4TUResearchData/djehuty/commit/672eaff0c058b3e71dabed0161faf505a5beb141))
- Prevent comments in query templates from being sent to the SPARQL endpoint. ([9ac7035](https://github.com/4TUResearchData/djehuty/commit/9ac703556e8f20a36c1fda6f5b77e165695e9001))

## [v25.1]

The January release of 2025 consists of 85 commits made by 3 authors. In this release we included an RPM package for Enterprise Linux 9. This RPM depends on packages in the [Extra Packages for Enterprise Linux (EPEL) repository](https://docs.fedoraproject.org/en-US/epel/).

### New features

- CodeMeta API output is more complete. ([91ed59d](https://github.com/4TUResearchData/djehuty/commit/91ed59d8650f70022131ede59d388bb1a5b76cd0), [860edfe](https://github.com/4TUResearchData/djehuty/commit/860edfec55ffa24be3609bc24c87a78e70587236), [3f150a2](https://github.com/4TUResearchData/djehuty/commit/3f150a246a4978d51df0ab658cba42c78a3b26a2), [5daa47e](https://github.com/4TUResearchData/djehuty/commit/5daa47e5f97a39cf2dc27eceb8314de0d0284b62))
- A second port to bind the web service on can now be configured. ([dff68a6](https://github.com/4TUResearchData/djehuty/commit/dff68a6d6bbf3f7548803857deeb1adb6cf9f320))
- Enable searching by author. ([18a242f](https://github.com/4TUResearchData/djehuty/commit/18a242fcde0f0bfa6036021c20d4eca91602d5a8), [fe09578](https://github.com/4TUResearchData/djehuty/commit/fe09578657d71894cec45cad36b4a62c10165a8b))
- Enable institution reviewing. ([cbd1092](https://github.com/4TUResearchData/djehuty/commit/cbd1092cccfacaf8d3191d1130fc1b34154b555b), [cb67f83](https://github.com/4TUResearchData/djehuty/commit/cb67f83bfa4749c3c468b430efe82f3fb4c34efc))
- Improve indexability by search engines. ([cc58483](https://github.com/4TUResearchData/djehuty/commit/cc58483902f0760673c2a91567991b18829b112a), [20fe6fd](https://github.com/4TUResearchData/djehuty/commit/20fe6fd9a5c6952af9368eae00755cc248c3c0a1))

### Bugfixes

- Related versions of a dataset are communicated to DataCite. ([1539117](https://github.com/4TUResearchData/djehuty/commit/1539117be2a7679bafa5a94366f79a832bd759c1))
- HTML output of the documentation is responsive to browser widths. ([934ed93](https://github.com/4TUResearchData/djehuty/commit/934ed9310f1153960b95aff4944a0a729d153549))
- Restore ability to create new collection versions. ([545de47](https://github.com/4TUResearchData/djehuty/commit/545de472c734161d223d94aa61b0d025eea07fec))
- Display embargoed datasets in the search results. ([c86dcf8](https://github.com/4TUResearchData/djehuty/commit/c86dcf85bee8af42988346cc12511341f1d3c6fc))
- Fixed building RPM packages. ([1f629fa](https://github.com/4TUResearchData/djehuty/commit/1f629fa0d0ea5acbb45b1ea5652f9cfe8bc431f3), [e4c1057](https://github.com/4TUResearchData/djehuty/commit/e4c10571a8da9c6b5c63e48d3bd1bce700ab0311))
- Fixed HTTP `PUT` behavior for `/v2/account/collections/<id>/articles`. ([107ea69](https://github.com/4TUResearchData/djehuty/commit/107ea693e170689b83213e668f9e75b59f9348c3))

### Technical debt

- Unified the development environment instructions between GNU/Linux, Windows and macOS. ([8921d35](https://github.com/4TUResearchData/djehuty/commit/8921d35c1a0909e331b4737b6c0bb6713fb77743), [ca9b583](https://github.com/4TUResearchData/djehuty/commit/ca9b5831c19948f098106917c34bc4ff383543d2))
- Run-time configurable properties are stored in a separate module. ([a8e353d](https://github.com/4TUResearchData/djehuty/commit/a8e353db6e29342adb038950eacf350e89dda7bf))
- Improve error handling. ([bdf77ed](https://github.com/4TUResearchData/djehuty/commit/bdf77edd810bb9d22c111b11e34e265c3e286f31), [23c3b53](https://github.com/4TUResearchData/djehuty/commit/23c3b53d297b11bacab08d2436b723637773a78d), [609c986](https://github.com/4TUResearchData/djehuty/commit/609c9864e357101f39e0dfb8cfc0b045889d9d17))
- Embed simplified 'zipfly'. ([0fe0904](https://github.com/4TUResearchData/djehuty/commit/0fe0904a2aa25fc19094ee2c57a1b1d6fda4b4ad))

## [v24.12]

### New features

- Add specific logging for when the server would respond an HTTP 500 error. ([1dcd141](https://github.com/4TUResearchData/djehuty/commit/1dcd141f7c75e82a5f970d0ac8ddba7e8915bf9c))

### Bugfixes

- Fix a problem with downloading Git repositories as ZIP. ([a8c2da4](https://github.com/4TUResearchData/djehuty/commit/a8c2da4c544b10a493d67c515a5fca191222ba29))
- Avoid returning an internal server error when using paging in the API. ([2629ef5](https://github.com/4TUResearchData/djehuty/commit/2629ef56ff43946067edf7e147f48867830691f6))
- Fix lay-out bug on the landing pages. ([a3ff6a5](https://github.com/4TUResearchData/djehuty/commit/a3ff6a54ee80359ad3d2299e968ab28766b86505))
- Fix bug when filtering on groups in the API. ([187f434](https://github.com/4TUResearchData/djehuty/commit/187f4344f5d0e50bcf7063f28dda9bfccc8229ae))

### Technical debt

- Refactor parts of the codebase. ([0370836](https://github.com/4TUResearchData/djehuty/commit/0370836d5bdff62f04f5815893658284aff3ca48), [dd7602a](https://github.com/4TUResearchData/djehuty/commit/dd7602a66691840ffe6c2d444a36dd4256c23627), [aa8eda2](https://github.com/4TUResearchData/djehuty/commit/aa8eda2fc0b5cf65cd38d4002d358e65312a845d), [3fb5163](https://github.com/4TUResearchData/djehuty/commit/3fb51635c82ad612681db5a3244d93e62cd8f616), [dd6ccca](https://github.com/4TUResearchData/djehuty/commit/dd6ccca45a7505b96e002a2bb79fc75b5384570c), [58c1fce](https://github.com/4TUResearchData/djehuty/commit/58c1fcedcec678d27c1d0daf9559dfab45fdb8f6))
- Reduce build-system files. ([e73966f](https://github.com/4TUResearchData/djehuty/commit/e73966fede6e1e2fc8ea2256f107b650a23400a0))
- Bump the minimal required Python version to 3.9. ([208c7e0](https://github.com/4TUResearchData/djehuty/commit/208c7e08f6162fd78a456079e079d5f609f67e68))
