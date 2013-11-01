#!/usr/bin/env python2

"""
InkTeX is an inkscape extension to render LaTeX code in inkscape documents.

InkTeX supports editing of LaTeX as well as arbitrary preambles. It requires

  * python2 > 2.5
  * inkscape
  * python-lxml
  * python-gtk2
  * either
    - pdflatex & pdf2svg
    or
    - latex & dvisvgm

At the present time, InkTeX runs only on unix derivates, however, it will
soon be made windows and OS X compatible.

InkTeX works by generating LaTeX code, compiling it, converting it into svg
and inserting the result into the inkscape document.
"""

import tempfile
import os
import subprocess as sp
import shutil
import copy
import time
import re

import pygtk
pygtk.require('2.0')
import gtk

from gtkcodebuffer import CodeBuffer, SyntaxLoader
import inkex


class Ui(object):
    """
    The user interface. This dialog is the LaTeX input window and includes
    widgets to display compilation logs and a preview. It uses GTK2 which
    must be installed an importable.
    """

    app_name = 'InkTeX'

    def __init__(self, render_callback, src):
        """Takes the following parameters:
          * render_callback: callback function to execute with "apply" button
          * src: source code that should be pre-inserted into the LaTeX input"""

        self.render_callback = render_callback
        self.src = src if src else ""

        # init the syntax highlighting buffer
        lang = SyntaxLoader("latex")
        self.syntax_buffer = CodeBuffer(lang=lang)

        self.setup_ui()

    def render(self, widget, data=None):
        """Extracts the input LaTeX code and calls the render callback. If that
        returns true, we quit and are happy."""

        buf = self.text.get_buffer()
        tex = buf.get_text(buf.get_start_iter(), buf.get_end_iter())

        if self.render_callback(tex):
            gtk.main_quit()
            return False

    def cancel(self, widget, data=None):
        """Close button pressed: Exit"""

        raise SystemExit(1)

    def destroy(self, widget, event, data=None):
        """Destroy hook for the GTK window. Quit and return False."""

        gtk.main_quit()
        return False

    def setup_ui(self):
        """Creates the actual UI."""

        # create a floating toplevel window and set some title and border
        self.window = gtk.Window(gtk.WINDOW_TOPLEVEL)
        self.window.set_type_hint(gtk.gdk.WINDOW_TYPE_HINT_DIALOG)
        self.window.set_title(self.app_name)
        self.window.set_border_width(8)

        # connect delete and destroy events
        self.window.connect("destroy", self.destroy)
        self.window.connect("delete-event", self.destroy)

        # This is our main container, vertically ordered.
        self.box_container = gtk.VBox(False, 5)
        self.box_container.show()

        self.notebook = gtk.Notebook()
        self.notebook.show()

        # First component: The input text view for the LaTeX code.
        # It lives in a ScrolledWindow so we can get some scrollbars when the
        # text is too long.
        self.text = gtk.TextView(self.syntax_buffer)
        self.text.get_buffer().set_text(self.src)
        self.text.show()
        self.text_container = gtk.ScrolledWindow()
        self.text_container.set_policy(gtk.POLICY_AUTOMATIC,
                                       gtk.POLICY_AUTOMATIC)
        self.text_container.set_shadow_type(gtk.SHADOW_IN)
        self.text_container.add(self.text)
        self.text_container.set_size_request(400, 200)
        self.text_container.show()

        self.notebook.append_page(self.text_container, gtk.Label("LaTeX"))

        # Second component: The log view
        self.log_view = gtk.TextView()
        self.log_view.show()
        self.log_container = gtk.ScrolledWindow()
        self.log_container.set_policy(gtk.POLICY_AUTOMATIC,
                                       gtk.POLICY_AUTOMATIC)
        self.log_container.set_shadow_type(gtk.SHADOW_IN)
        self.log_container.add(self.log_view)
        self.log_container.set_size_request(400, 200)
        self.log_container.show()

        self.notebook.append_page(self.log_container, gtk.Label("Log"))

        # third component: settings
        self.settings_container = gtk.Table(2,2)
        self.settings_container.show()
        self.label_preamble = gtk.Label("Preamble")
        self.label_preamble.set_alignment(0, 0.5)
        self.label_preamble.show()
        self.preamble = gtk.FileChooserButton("...")
        self.preamble.set_action(gtk.FILE_CHOOSER_ACTION_OPEN)
        self.preamble.show()
        self.settings_container.attach(self.label_preamble, yoptions=gtk.SHRINK,
            left_attach=0, right_attach=1, top_attach=0, bottom_attach=1)
        self.settings_container.attach(self.preamble, yoptions=gtk.SHRINK,
            left_attach=1, right_attach=2, top_attach=0, bottom_attach=1)

        self.label_scale = gtk.Label("Scale")
        self.label_scale.set_alignment(0, 0.5)
        self.label_scale.show()
        self.scale_adjustment = gtk.Adjustment(value=1.0, lower=0, step_incr=0.1)
        self.scale = gtk.SpinButton(adjustment=self.scale_adjustment, digits=1)
        self.scale.show()
        self.settings_container.attach(self.label_scale, yoptions=gtk.SHRINK,
            left_attach=0, right_attach=1, top_attach=1, bottom_attach=2)
        self.settings_container.attach(self.scale, yoptions=gtk.SHRINK,
            left_attach=1, right_attach=2, top_attach=1, bottom_attach=2)

        self.notebook.append_page(self.settings_container, gtk.Label("Settings"))

        self.box_container.pack_start(self.notebook, True, True)

        # separator between buttonbar and notebook
        self.separator_buttons = gtk.HSeparator()
        self.separator_buttons.show()

        self.box_container.pack_start(self.separator_buttons, False, False)

        # the button bar
        self.box_buttons = gtk.HButtonBox()
        self.box_buttons.set_layout(gtk.BUTTONBOX_END)
        self.box_buttons.show()

        self.button_render = gtk.Button(stock=gtk.STOCK_APPLY)
        self.button_cancel = gtk.Button(stock=gtk.STOCK_CLOSE)
        self.button_render.set_flags(gtk.CAN_DEFAULT)
        self.button_render.connect("clicked", self.render, None)
        self.button_cancel.connect("clicked", self.cancel, None)
        self.button_render.show()
        self.button_cancel.show()

        self.box_buttons.pack_end(self.button_cancel)
        self.box_buttons.pack_end(self.button_render)

        self.box_container.pack_start(self.box_buttons, False, False)

        self.window.add(self.box_container)
        self.window.set_default(self.button_render)
        self.window.show()

    def log(self, msg):
        buffer = self.log_view.get_buffer()
        buffer.set_text(msg)
        self.notebook.set_current_page(1)

    def main(self):
        gtk.main()


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
                \begin{document}
                \pagestyle{empty}
                \noindent
                    %s
                \end{document}"""

    tex_file = 'inktex.tex'
    pdf_file = 'inktex.pdf'
    dvi_file = 'inktex.dvi'
    svg_file = 'inktex.svg'

    inktex_namespace = u'http://www.oelerich.org/inktex'
    svg_namespace = u'http://www.w3.org/2000/svg'
    xlink_namespace = u'http://www.w3.org/1999/xlink'

    namespaces = {
        u'inktex': inktex_namespace,
        u'svg': svg_namespace,
        u'xlink': xlink_namespace,
    }

    compiler_pdf = 'pdflatex %s' % tex_file
    converter_pdf = 'pdf2svg %s %s' % (pdf_file, svg_file)
    compiler_dvi = 'latex %s' % tex_file
    converter_dvi = 'dvisvgm -n %s' % dvi_file

    def __init__(self):
        # find out which compiler/converter we'll use
        devnull = open(os.devnull, 'w')

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

    def render(self, src):
        """Executes some functions in order"""

        self.write_latex(src)
        self.compile()
        self.convert()
        return self.get_svg_group()

    def write_latex(self, tex_code):
        """Generate the latex file"""

        f = open(os.path.join(self.tmp_dir, self.tex_file), 'w')
        f.write(self.skeleton % tex_code)
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


    def get_svg_group(self):
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

        return copy.copy(master_group)

    def scramble_ids(self, root):
        """Here, we assign new ids to the elements in the newly generated
        svg object. We also have to update references and links."""

        href_map = dict()
        ns = self.namespaces
        xlink_key = '{%s}href' % self.xlink_namespace
        clip_path_key = 'clip_path'

        # Map items to new ids
        for i, el in enumerate(root.xpath('//*[attribute::id]')):
            cur_id = el.attrib['id']
            new_id = '%s-%s' % (time.time(), i)
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

        self.ui = Ui(self.render, self.orig_src)
        self.ui.main()

    def render(self, tex):
        """Execute the rendering and, upon errors, send them to the UI"""

        self.new_src = tex

        with Converter() as renderer:
            try:
                self.new = renderer.render(self.new_src)

                self.copy_styles()
                self.store_inktex_information()
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

        src_attrib = '{%s}src' % Converter.inktex_namespace
        g_tag = '{%s}g' % Converter.svg_namespace

        for i in self.options.ids:
            node = self.selected[i]

            if node.tag == g_tag and src_attrib in node.attrib:
                return node, \
                       node.attrib.get(src_attrib, '').decode('string-escape')

        return None, None

    def store_inktex_information(self):
        """Store the LaTeX source in the top level element."""

        self.new.attrib['{%s}src' % Converter.inktex_namespace] = \
            self.new_src.encode('string-escape')

    def copy_styles(self):
        """Copy the styles and transforms if we edited an old element.
        This can be extended further, to include colors etc."""

        self.ui.log("Hallo")

        transform_attrib = 'transform'
        transform_attrib_ns = '{%s}transform' % Converter.svg_namespace
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



if __name__ == "__main__":
    it = InkTex()
    it.affect()