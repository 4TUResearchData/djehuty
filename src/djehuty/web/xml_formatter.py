"""
This module implements constructing XML trees for rendering the DataCite
and other XML formats.
"""

from xml.etree import ElementTree
from djehuty.utils.convenience import value_or, value_or_none

class ElementMaker:
    '''
    Convenience class to simplify construction of xml trees. The number of
    steps is reduced by combining common ltree operations in a single call.
    An instance of this class can hold a set of namespace definitions,
    enabling tree construction using prefixes instead of full namespaces
    in element and attribute names. Default namespace is also obeyed.
    '''
    def __init__ (self, namespaces=None):
        self.namespaces = namespaces
        if self.namespaces is None:
            self.namespaces = {}

        for prefix, uri in self.namespaces.items():
            ElementTree.register_namespace(prefix, uri)

    def resolve (self, name, is_element=True):
        """Procedure to translate a prefixed NAME to its full namespace URI."""
        if ':' in name:
            prefix, suffix = name.split(':' ,1)
            if prefix != 'xml':
                return f'{{{self.namespaces[prefix]}}}{suffix}'

        if is_element and '' in self.namespaces:
            return f'{{{self.namespaces[""]}}}{name}'

        return name

    def child (self, parent, name, attrib=None, text=None):
        """Procedure to process a child element including attributes."""
        if parent is not None:
            element = ElementTree.SubElement(parent, self.resolve(name))
        else:
            element = ElementTree.Element(self.resolve(name))

        if attrib is not None:
            for attname, val in attrib.items():
                element.set(self.resolve(attname, False), val)

        if text:
            element.text = f"{text}"

        return element

    def child_option (self, parent, name, source, key, attrib=None):
        """Procedure to process a child element if KEY exists in SOURCE."""
        if key in source:
            return self.child(parent, name, attrib, f"{source[key]}")
        return None

    def root (self, name, attrib=None, schemas=None, text=None):
        """Procedure to make the ElementTree root."""
        attrib = attrib if attrib else {}
        if schemas:
            self.namespaces['xsi'] = 'http://www.w3.org/2001/XMLSchema-instance'
            ElementTree.register_namespace('xsi', self.namespaces['xsi'])
            schema_decl = ''.join(
                [f'{self.namespaces[pr]} {schema}' for pr, schema in schemas.items()])
            attrib['xsi:schemaLocation'] = schema_decl
        return self.child(None, name, attrib, text)

def serialize_tree_to_string (tree, indent=True):
    """Procedure to turn the ElementTree into a string."""
    if indent:
        ElementTree.indent(tree)
    return ElementTree.tostring(tree, encoding='utf8', short_empty_elements=True)

def scrub (obj):
    """Eliminate from construct of dicts and lists all values x for which bool(x)==False."""
    if isinstance(obj, dict):
        scrubbed = {key:scrub(val) for key,val in obj.items() if val}
        return {key:val for key,val in scrubbed.items() if val}

    if isinstance(obj, list):
        scrubbed = [scrub(val) for val in obj if val]
        return [val for val in scrubbed if val]

    return obj

def dublincore_tree (parameters):
    """Procedure to create a Dublin Core XML tree from PARAMETERS."""
    parameters = scrub(parameters)
    namespaces = {'dc' : 'http://purl.org/dc/elements/1.1/',
                  'oai': 'http://www.openarchives.org/OAI/2.0/oai_dc/'}
    schemas =    {'oai': 'https://www.openarchives.org/OAI/2.0/oai_dc.xsd'}
    maker = ElementMaker(namespaces)
    root = maker.root('oai:dc', schemas=schemas)
    item = parameters['item']
    maker.child(root, 'dc:title', {}, item['title'])
    for creator in value_or (parameters, 'authors', []):
        maker.child_option(root, 'dc:creator', creator, 'full_name')
    for tag in value_or (parameters, 'tags', []):
        maker.child(root, 'dc:subject', {}, tag)
    maker.child(root, 'dc:description', {}, item['description'])
    maker.child(root, 'dc:publisher', {}, value_or(item, 'publisher', '4TU.ResearchData'))
    for contributor in value_or (parameters, 'contributor', []):
        maker.child(root, 'dc:contributor', {}, contributor['name'])
    for name in value_or (parameters, 'organizations', []):
        maker.child(root, 'dc:contributor', {}, name)
    if 'published_date' in parameters:
        maker.child(root, 'dc:date', {}, parameters['published_date'])
    maker.child(root, 'dc:type', {}, item['defined_type_name'])
    maker.child_option(root, 'dc:format', item, 'format')
    maker.child(root, 'dc:identifier', {}, parameters['doi'])
    maker.child(root, 'dc:language', {}, value_or(item, 'language', 'en'))
    if 'recource_doi' in item:
        maker.child(root, 'dc:relation', {}, f"https://doi.org/{item['recource_doi']}")
    maker.child_option(root, 'dc:coverage', item, 'geolocation')
    maker.child_option(root, 'dc:coverage', item, 'time_coverage')
    maker.child_option(root, 'dc:rights', item, 'license_name')
    return root

def dublincore (parameters):
    """Procedure to create a Dublin Core XML string from PARAMETERS."""
    return serialize_tree_to_string (dublincore_tree (parameters))

def nlm (parameters):
    """Procedure to create a NLM XML string from PARAMETERS."""
    parameters = scrub(parameters)
    namespaces = {'xlink': 'http://www.w3.org/1999/xlink/'}
    maker = ElementMaker(namespaces)
    root    = maker.root('articles')
    article = maker.child(root, 'article')
    front   = maker.child(article, 'front')
    meta    = maker.child(front, 'article-meta')
    item = parameters['item']
    maker.child(maker.child(meta, 'title-group'),
                'article-title', {}, item['title'])
    contribs = maker.child(meta, 'contrib-group')
    authors = parameters['authors']
    for author in authors:
        name = maker.child(maker.child(contribs, 'contrib', {'contrib-type': 'author'}),
                           'name')
        maker.child_option(name, 'surname', author, 'last_name')
        maker.child_option(name, 'given-name', author, 'first_name')
    maker.child(maker.child(meta, 'pub-date', {'pub-type': 'pub'}),
                'year', {}, value_or(parameters, 'published_year', None))
    maker.child(meta, 'self-uri', {'xlink:href': f"https:doi.org/{parameters['doi']}"})
    maker.child(front, 'abstract', {}, item['description'])
    return serialize_tree_to_string(root)

def refworks (parameters):
    """Procedure to create a Refworks XML string from PARAMETERS."""
    parameters = scrub(parameters)
    maker = ElementMaker()
    root = maker.root('references')
    ref  = maker.child(root, 'reference')
    item    = parameters['item']
    authors = parameters['authors']
    for index, author in enumerate(authors):
        name = author['full_name']
        if 'last_name' in author and 'first_name' in author:
            name = f"{author['last_name']}, {author['first_name']}"
        maker.child(ref, f'a{index+1}', {}, name)
    maker.child(ref, 't1', {}, item['title'])
    maker.child(ref, 'sn')
    maker.child(ref, 'op')
    maker.child(ref, 'vo')
    maker.child(ref, 'ab', {}, item['description'])
    maker.child(ref, 'la', {}, value_or(item, 'language', 'en'))
    if 'tags' in parameters:
        for index, tag in enumerate(parameters['tags']):
            maker.child(ref, f'k{index+1}', {}, tag)
    maker.child(ref, 'pb')
    maker.child(ref, 'pp')
    maker.child(ref, 'yr', {}, parameters['published_year'])
    maker.child(ref, 'ed')
    doi = parameters['doi']
    maker.child(ref, 'ul', {}, f'https://doi.org/{doi}')
    maker.child(ref, 'do', {}, doi)
    return serialize_tree_to_string(root)

def datacite_tree (parameters, debug=False):
    """Procedure to create a DataCite XML tree from PARAMETERS."""
    parameters = scrub(parameters)
    namespaces = {'': 'http://datacite.org/schema/kernel-4'}
    schemas    = {'': 'http://schema.datacite.org/meta/kernel-4.4/metadata.xsd'}
    maker = ElementMaker(namespaces)
    root = maker.root('resource', schemas=schemas)
    item = parameters['item']

    #01 identifier
    maker.child(root, 'identifier', {'identifierType':'DOI'}, parameters['doi'])

    #02 creators
    orcid_att = {'nameIdentifierScheme': 'https://orcid.org/'}
    personal_att = {'nameType': 'Personal'}
    creators = parameters['authors']
    creators_element = maker.child(root,'creators')
    for creator in creators:
        creator_att = personal_att if 'orcid_id' in creator else {}
        creator_element = maker.child(creators_element, 'creator')
        maker.child_option(creator_element, 'creatorName', creator, 'full_name', creator_att)
        maker.child_option(creator_element, 'givenName', creator, 'first_name')
        maker.child_option(creator_element, 'familyName', creator, 'last_name')
        maker.child_option(creator_element, 'nameIdentifier', creator, 'orcid_id', orcid_att)

    #03 titles
    maker.child(maker.child(root, 'titles'), 'title', {}, item['title'])

    #04 publisher
    maker.child(root, 'publisher', {}, value_or(item, 'publisher', '4TU.ResearchData'))

    #05 publicationYear
    maker.child(root, 'publicationYear', {}, value_or(parameters, 'published_year', None))

    #06 resourceType
    rtype = value_or(item, 'defined_type_name', 'Collection').capitalize()
    if rtype not in ('Dataset','Software','Collection'):
        rtype = 'Text'
    maker.child(root, 'resourceType', {'resourceTypeGeneral': rtype}, rtype)

    #07 subjects
    subjects_element = maker.child(root, 'subjects')
    if 'categories' in parameters:
        for cat in parameters['categories']:
            maker.child(
                subjects_element,
                'subject',
                { 'subjectScheme'     :
                  'Australian and New Zealand Standard Research Classification (ANZSRC), 2008',
                  'classificationCode': cat['classification_code'] },
                cat['title']
            )
    if 'tags' in parameters:
        for tag in parameters['tags']:
            maker.child(subjects_element, 'subject', {}, tag)
    if 'time_coverage' in item:
        maker.child(subjects_element, 'subject', {}, f"Time: {item['time_coverage']}")

    #08 contributors
    has_organizations = 'organizations' in parameters
    has_contributors = 'contributors' in parameters
    if has_organizations or has_contributors:
        contributors_element = maker.child(root, 'contributors')
        type_att = {'contributorType': 'Other'}
        orcid_att = {'nameIdentifierScheme': 'https://orcid.org/'}
        if has_contributors:
            for contributor in parameters['contributors']:
                contributor_element = maker.child(contributors_element, 'contributor', type_att)
                name = contributor['name']
                orcid = value_or_none(contributor, 'orcid')
                maker.child(contributor_element, 'contributorName', {'nameType': 'Personal'}, name)
                if orcid:
                    maker.child(contributor_element, 'nameIdentifier', orcid_att, orcid)
        if has_organizations:
            for name in parameters['organizations']:
                contributor_element = maker.child(contributors_element, 'contributor', type_att)
                maker.child(contributor_element, 'contributorName',
                            {'nameType': 'Organizational'}, name)

    #09 dates
    if 'published_date' in parameters:
        maker.child(maker.child(root, 'dates'), 'date',
                    {'dateType': 'Issued'}, parameters['published_date'])

    #10 language
    if 'language' in item:
        maker.child(root, 'language', {}, item['language'])

    #11 relatedIdentifiers
    has_doi = 'resource_doi' in item
    has_ref = 'references' in parameters
    if has_doi or has_ref:
        relations_element = maker.child(root, 'relatedIdentifiers')
        if has_doi:
            maker.child(relations_element,
                        'relatedIdentifier',
                        {'relatedIdentifierType': 'DOI', 'relationType': 'IsSupplementTo'},
                        item['resource_doi'])
        if has_ref:
            for ref in parameters['references']:
                maker.child(relations_element,
                            'relatedIdentifier',
                            {'relatedIdentifierType': 'URL', 'relationType': 'References'},
                            ref['url'])

    #12 formats
    if 'format' in item:
        maker.child(maker.child(root, 'formats'), 'format', {}, item['format'])

    #13 version
    maker.child(root, 'version', {}, f'{item["version"]}')

    #14 rightsList
    if 'license_id' in item:
        maker.child(maker.child(root, 'rightsList'),
                    'rights',
                    {'rightsURI': item['license_url']},
                    item['license_name'])

    #15 descriptions
    maker.child(maker.child(root, 'descriptions'),
                'description',
                {'descriptionType': 'Abstract'},
                item['description'])

    #16 geoLocations
    has_geo = 'geolocation' in item
    coordinates = value_or(parameters, 'coordinates', {})
    has_point = 'lat_valid' in coordinates and 'lon_valid' in coordinates
    if has_geo or has_point:
        geo_element = maker.child(maker.child(root, 'geoLocations'), 'geoLocation')
        if has_geo:
            maker.child(geo_element, 'geoLocationPlace', {}, item['geolocation'])
        if has_point:
            point_element = maker.child(geo_element, 'geoLocationPoint')
            maker.child(point_element, 'pointLongitude', {}, coordinates['lon_valid'])
            maker.child(point_element, 'pointLatitude', {}, coordinates['lat_valid'])

    #17 fundingReferences
    if 'fundings' in parameters:
        fundings_element = maker.child(root, 'fundingReferences')
        for funding in parameters['fundings']:
            funding_element = maker.child(fundings_element, 'fundingReference')
            maker.child(funding_element, 'funderName', {},
                        value_or(funding, 'funder_name', 'unknown'))
            maker.child_option(funding_element, 'awardNumber', funding, 'grant_code')
            maker.child_option(funding_element, 'awardTitle', funding, 'title')

    #debug
    if debug:
        param_strings = [f'{key:<15}: {val}' for key, val in parameters.items()]
        root.insert(0, ElementTree.Comment('DEBUG\n' + '\n'.join(param_strings)))

    return root

def datacite (parameters, indent=True):
    """Procedure to create a DataCite XML string from PARAMETERS.
       For registration at Datacite, set indent to False"""
    return serialize_tree_to_string (datacite_tree(parameters), indent=indent)
