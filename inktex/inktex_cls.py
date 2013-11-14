import inkex

from converter import Converter
from ui import Ui


class InkTex(inkex.Effect):
    """
    Our main class, derived from inkex.Effect. It wraps the other classes and
    implements the effect() function.
    """

    def __init__(self):
        inkex.Effect.__init__(self)

        # the original (i.e., selected) svg element and the newly created one
        # including the original LaTeX source.
        self.orig = None
        self.orig_src = None
        self.new = None
        self.new_src = None

    def effect(self):
        """If there is an original element, store it. Open the GUI."""

        self.orig, self.orig_src = self.get_original()

        self.ui = Ui(self.render, self.orig_src, self.get_settings())
        self.ui.main()

    def render(self, tex, settings):
        """Execute the rendering and, upon errors, send them to the UI"""

        self.new_src = tex
        self.store_settings(settings)

        with Converter(self) as renderer:
            try:
                self.new = renderer.render(self.new_src, settings)
                self.copy_styles()
                self.store_src_information()
                self.append_or_replace()

                return True
            except Exception, e:
                self.ui.log(e.message)

    def append_or_replace(self):
        """Appends the new object to the document or, if we edited an old
        one, replace the old one."""

        if self.orig is not None:
            parent = self.orig.getparent()
            parent.remove(self.orig)
            parent.append(self.new)
        else:
            self.current_layer.append(self.new)

    def error(self, msg):
        """Display an error in the UI"""

        inkex.errormsg(msg)

    def get_original(self):
        """Here, we try to find inktex objects among the selected svg elements
        when the dialog was opened."""

        src_attrib = Converter.add_ns('src', ns=u'inktex')
        g_tag = Converter.add_ns('g', ns=u'svg')

        for i in self.options.ids:
            node = self.selected[i]

            if node.tag == g_tag and src_attrib in node.attrib:
                return node, \
                       node.attrib.get(src_attrib, '').decode('string-escape')

        return None, None

    def get_settings(self):
        """Gets a dictionary with the inktex settings stored in the
        svg/metadata part of the svg doc."""

        settings = {}

        try:
            attribs = self.document.xpath('//inktex:settings',
                namespaces=Converter.namespaces)[0].attrib

            for key, value in attribs.iteritems():
                settings[key[key.find('}')+1:]] = value
            return settings
        except:
            return {}

    def store_settings(self, settings):
        """Store a dict of inktex settings in the svg tree"""

        # find or create svg/metadata/inktex:settings
        try:
            inktex_settings = self.document.xpath('//inktex:settings',
                namespaces=Converter.namespaces)[0]
        except:
            metadata = self.xpathSingle('//svg:metadata')
            inktex_settings = inkex.etree.SubElement(metadata,
                Converter.add_ns('settings', ns=u'inktex'))

        # small helper function to store settings
        def store_setting(name, value):
            inktex_settings.attrib[Converter.add_ns(name, ns=u'inktex')] = str(value)

        # store settings
        for key, value in settings.iteritems():
            store_setting(key, value)

    def store_src_information(self):
        """Store the LaTeX source in the top level element."""

        self.new.attrib[Converter.add_ns('src', ns=u'inktex')] = \
            self.new_src.encode('string-escape')


    def copy_styles(self):
        """Copy the styles and transforms if we edited an old element.
        This can be extended further, to include colors etc."""

        transform_attrib = 'transform'
        transform_attrib_ns = Converter.add_ns('transform', ns=u'svg')
        style_attrib = 'style'

        if self.orig is None:
            return

        if transform_attrib in self.orig.attrib:
            self.new.attrib[transform_attrib] = \
                self.orig.attrib[transform_attrib]

        if transform_attrib_ns in self.orig.attrib:
            self.new.attrib[transform_attrib] = \
                self.orig.attrib[transform_attrib_ns]

        if style_attrib in self.orig.attrib:
            self.new.attrib[style_attrib] = self.orig.attrib[style_attrib]

