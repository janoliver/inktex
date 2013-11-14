import tempfile
import os
import subprocess as sp
import shutil
import copy
import re

import inkex


class CompilerException(Exception):
    """
    Exception thrown, when the latex compilation failed.
    """
    pass

class ConverterException(Exception):
    """
    Exception thrown, when the dvi/pdf to svg convertion failed
    """
    pass

class DependencyException(Exception):
    """
    Exception thrown, when not converter/compiler can be found
    """
    pass

class Converter(object):
    """
    This class is responsible for creating a temporary folder, generating the
    latex document, compiling it and converting it into svg.
    The class should be used with a with statement, so temporary stuff can
    be cleaned up:

        with Converter() as conv:
            conv.run()
    """

    skeleton = r"""\documentclass{article}
                %s
                \begin{document}
                \pagestyle{empty}
                \noindent
                    %s
                \end{document}"""

    tex_file = 'inktex.tex'
    pdf_file = 'inktex.pdf'
    dvi_file = 'inktex.dvi'
    svg_file = 'inktex.svg'

    namespaces = dict(inkex.NSS.items() + {
        u'inktex': u'http://www.oelerich.org/inktex'
    }.items())

    compiler_pdf = 'pdflatex %s' % tex_file
    converter_pdf = 'pdf2svg %s %s' % (pdf_file, svg_file)
    compiler_dvi = 'latex %s' % tex_file
    converter_dvi = 'dvisvgm -n %s' % dvi_file

    def add_ns(tag, ns=None):
        """Adds the namespace to an object"""

        if inkex.NSS.has_key(ns):
            return inkex.addNS(tag, ns=ns)
        elif Converter.namespaces.has_key(ns):
            return '{%s}%s' % (Converter.namespaces[ns], tag)
        else:
            return tag
    add_ns = staticmethod(add_ns)

    def __init__(self, effect_class):
        # find out which compiler/converter we'll use
        devnull = open(os.devnull, 'w')

        self.effect_class = effect_class
        self.compiler = None
        self.converter = None

        # try svg executables
        try:
            sp.call(self.compiler_dvi.split(" "),
                            stdout=devnull, stderr=devnull)
            sp.call(self.converter_dvi.split(" "),
                            stdout=devnull, stderr=devnull)

            self.compiler = self.compiler_dvi.split(" ")
            self.converter = self.converter_dvi.split(" ")

            return
        except:
            pass

        # try pdf executables
        try:
            sp.call(self.compiler_pdf.split(" "),
                            stdout=devnull, stderr=devnull)
            sp.call(self.converter_pdf.split(" "),
                            stdout=devnull, stderr=devnull)

            self.compiler = self.compiler_pdf.split(" ")
            self.converter = self.converter_pdf.split(" ")

            return
        except:
            pass

        raise DependencyException()

    def __enter__(self):
        """Create temporary directory for the convertion"""

        self.tmp_dir = tempfile.mkdtemp()
        return self

    def __exit__(self, type, value, traceback):
        """Clean up temporary files"""

        shutil.rmtree(self.tmp_dir)

    def render(self, src, settings):
        """Executes some functions in order"""

        # find preamble code
        preamble_code = ""
        if 'preamble' in settings and os.path.exists(settings['preamble']):
            with open(settings['preamble'], "r") as preamble_file:
                preamble_code = preamble_file.read()

        scale_factor = 1.0
        if 'scale' in settings:
            scale_factor = settings['scale']

        self.write_latex(src, preamble_code)
        self.compile()
        self.convert()
        return self.get_svg_group(scale_factor)

    def write_latex(self, tex_code, preamble_code):
        """Generate the latex file"""

        f = open(os.path.join(self.tmp_dir, self.tex_file), 'w')
        f.write(self.skeleton % (preamble_code, tex_code))
        f.close()

    def compile(self):
        """compile the latex file. Raise CompilerException on errors"""

        proc = sp.Popen(
            self.compiler, cwd=self.tmp_dir,
            stdout=sp.PIPE, stderr=sp.PIPE,
            stdin=sp.PIPE
        )

        out, err = proc.communicate()

        if proc.returncode:
            raise CompilerException(out)

    def convert(self):
        """Convert the generated file to svg. Raise ConverterException on err"""

        # check, which path we are going to take.


        proc = sp.Popen(
            self.converter, cwd=self.tmp_dir,
            stdout=sp.PIPE, stderr=sp.PIPE,
            stdin=sp.PIPE
        )

        out, err = proc.communicate()

        if proc.returncode:
            raise ConverterException(out)


    def get_svg_group(self, scale=1.0):
        """this function parses the generated svg and returns a single
        svg group with all its contents. The ids of the elements are
        made unique so we don't run into problems in inkscape later."""

        tree = inkex.etree.parse(os.path.join(self.tmp_dir, self.svg_file))
        root = tree.getroot()

        self.scramble_ids(root)

        master_group = inkex.etree.SubElement(root, 'g')
        for c in root:
            if c is not master_group:
                master_group.append(c)

        # apply scaling
        if scale != 1.0:
            master_group.attrib['transform'] = 'scale(%f,%f)' % (scale, scale)

        return copy.copy(master_group)

    def scramble_ids(self, root):
        """Here, we assign new ids to the elements in the newly generated
        svg object. We also have to update references and links."""

        href_map = dict()
        ns = self.namespaces
        xlink_key = Converter.add_ns('href', ns=u'xlink')
        clip_path_key = 'clip_path'

        # Map items to new ids
        for i, el in enumerate(root.xpath('//*[attribute::id]')):
            cur_id = el.attrib['id']
            new_id = self.effect_class.uniqueId(cur_id)
            href_map['#' + cur_id] = "#" + new_id
            el.attrib['id'] = new_id

        # Replace hrefs
        url_re = re.compile('^url\((.*)\)$')

        for el in root.xpath('//*[attribute::xlink:href]', namespaces=ns):
            cur_href = el.attrib[xlink_key]
            el.attrib[xlink_key] = href_map.get(cur_href, cur_href)

        for el in root.xpath('//*[attribute::svg:clip-path]', namespaces=ns):
            m = url_re.match(el.attrib['clip-path'])
            if m:
                el.attrib[clip_path_key] = 'url(%s)' % href_map.get(
                    m.group(1), m.group(1)
                )
