from xml.etree import ElementTree

from djehuty.web import xml_formatter

NAMESPACE = {"d": "http://datacite.org/schema/kernel-4"}


def _parameters(**extra):
    parameters = {
        "doi": "10.4121/example",
        "item": {"title": "Example", "version": 1, "description": "Text"},
        "published_year": "2026",
    }
    parameters.update(extra)
    return parameters


def _dates(parameters):
    tree = xml_formatter.datacite_tree(parameters)
    root = ElementTree.fromstring(ElementTree.tostring(tree))
    return root.findall("d:dates/d:date", NAMESPACE)


class TestDataCiteDates:
    def test_issued_only_without_withdrawn(self):
        dates = _dates(_parameters(published_date="2026-04-01"))
        assert [(d.get("dateType"), d.text) for d in dates] == [("Issued", "2026-04-01")]

    def test_withdrawn_is_added_beside_issued(self):
        withdrawn = {"date": "2026-11-09", "reason": "Retracted."}
        dates = _dates(_parameters(published_date="2026-04-01", withdrawn=withdrawn))
        assert [(d.get("dateType"), d.text) for d in dates] == [
            ("Issued", "2026-04-01"),
            ("Withdrawn", "2026-11-09"),
        ]
        assert dates[1].get("dateInformation") == "Retracted."

    def test_withdrawn_without_published_date(self):
        withdrawn = {"date": "2026-11-09", "reason": "Retracted."}
        dates = _dates(_parameters(withdrawn=withdrawn))
        assert [(d.get("dateType"), d.text) for d in dates] == [("Withdrawn", "2026-11-09")]

    def test_no_dates_element_when_neither_is_given(self):
        assert _dates(_parameters()) == []
