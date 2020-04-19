from lxml import etree

from ebook_converter.ebooks.oeb.polish.container import OPF_NAMESPACES
from ebook_converter.utils.localization import canonicalize_lang


__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'


def get_book_language(container):
    for lang in container.opf_xpath('//dc:language'):
        raw = lang.text
        if raw:
            code = canonicalize_lang(raw.split(',')[0].strip())
            if code:
                return code


def set_guide_item(container, item_type, title, name, frag=None):
    ref_tag = '{%s}reference' % OPF_NAMESPACES['opf']
    href = None
    if name:
        href = container.name_to_href(name, container.opf_name)
        if frag:
            href += '#' + frag

    guides = container.opf_xpath('//opf:guide')
    if not guides and href:
        g = container.opf.makeelement('{%s}guide' % OPF_NAMESPACES['opf'], nsmap={'opf':OPF_NAMESPACES['opf']})
        container.insert_into_xml(container.opf, g)
        guides = [g]

    for guide in guides:
        matches = []
        for child in guide.iterchildren(etree.Element):
            if child.tag == ref_tag and child.get('type', '').lower() == item_type.lower():
                matches.append(child)
        if not matches and href:
            r = guide.makeelement(ref_tag, type=item_type, nsmap={'opf':OPF_NAMESPACES['opf']})
            container.insert_into_xml(guide, r)
            matches.append(r)
        for m in matches:
            if href:
                m.set('title', title), m.set('href', href), m.set('type', item_type)
            else:
                container.remove_from_xml(m)
    container.dirty(container.opf_name)

