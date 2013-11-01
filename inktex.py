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
import subprocess
import shutil
import copy
import time

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
        """
        Takes the following parameters:
          * render_callback: callback function to execute with "apply" button
          * src: source code that should be pre-inserted into the LaTeX input
        """
        self.render_callback = render_callback
        self.src = src if src else ""

        # init the syntax highlighting buffer
        lang = SyntaxLoader("latex")
        self.syntax_buffer = CodeBuffer(lang=lang)

        self.setup_ui()

    def render(self, widget, data=None):
        """
        Extracts the input LaTeX code and calls the render callback. If that
        returns true, we quit and are happy.
        """
        buf = self.text.get_buffer()
        tex = buf.get_text(buf.get_start_iter(), buf.get_end_iter())

        if self.render_callback(tex):
            gtk.main_quit()
            return False

    def cancel(self, widget, data=None):
        """
        Close button pressed: Exit
        """
        raise SystemExit(1)

    def destroy(self, widget, event, data=None):
        """
        Destroy hook for the GTK window. Quit and return False.
        """
        gtk.main_quit()
        return False

    def setup_ui(self):
        """
        Creates the actual UI.
        """

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

        self.box_container.pack_start(self.text_container, True, True)

        # separator between buttonbar and textview
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

class Converter(object):
    """
    This class is responsible for creating a temporary folder, generating the
    latex document, compiling it and converting it into svg.
    """

    skeleton = r"""\documentclass{article}
                \begin{document}
                \pagestyle{empty}
                \noindent
                    %s
                \end{document}"""

    tex_file = 'inktex.tex'
    pdf_file = 'inktex.pdf'
    svg_file = 'inktex.svg'

    inktex_src_namespace = u'{http://www.oelerich.org/inktex}src'
    svg_g_namespace = u'{http://www.w3.org/2000/svg}g'

    compiler = 'pdflatex'
    converter = 'pdf2svg'

    def __enter__(self):
        self.tmp_dir = tempfile.mkdtemp()
        return self

    def __exit__(self, type, value, traceback):
        shutil.rmtree(self.tmp_dir)

    def write_latex(self, tex_code):
        f = open(os.path.join(self.tmp_dir, self.tex_file), 'w')
        f.write(self.skeleton % tex_code)
        f.close()

    def compile(self):
        proc_latex = subprocess.Popen(
            [self.compiler, self.tex_file], cwd=self.tmp_dir,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE
        )

        latex_out, latex_err =  proc_latex.communicate()

        if proc_latex.returncode:
            raise CompilerException(latex_err)

        proc_pdf2svg = subprocess.Popen(
            [self.converter, self.pdf_file, self.svg_file], cwd=self.tmp_dir,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE
        )

        pdf2svg_out, pdf2svg_err =  proc_pdf2svg.communicate()

        if proc_latex.returncode:
            raise ConverterException(pdf2svg_err)

    def get_svg_group(self, tex):
        tree = inkex.etree.parse(os.path.join(self.tmp_dir, self.svg_file))
        root = tree.getroot()

        self.scramble_ids(root)

        master_group = inkex.etree.SubElement(root, 'g')
        for c in root:
            if c is master_group:
                continue
            master_group.append(c)

        # add information
        master_group.attrib[self.inktex_src_namespace] = tex.encode('string-escape')

        return copy.copy(master_group)

    def scramble_ids(self, root):
        for i, el in enumerate(root.xpath('//*[attribute::id]')):
            el.attrib['id'] = '%s-%s' % (time.time(), i)

class InkTex(inkex.Effect):
    skeleton = r"""\documentclass{article}
                \begin{document}
                \pagestyle{empty}
                \noindent
                    %s
                \end{document}"""

    def __init__(self):
        inkex.Effect.__init__(self)
        self.orig = None

    def effect(self):
        self.orig, src = self.get_original()

        self.ui = Ui(self.render, src)
        self.ui.main()

    def render(self, tex):
        with Converter() as renderer:
            renderer.write_latex(tex)

            try:
                renderer.compile()
                svg_tree = renderer.get_svg_group(tex)
                self.append_or_replace(svg_tree)
                return True
            except Exception, e:
                self.error(e.message)

    def append_or_replace(self, object):
        if self.orig is not None:
            parent = self.orig.getparent()
            parent.remove(self.orig)
            parent.append(object)
        else:
            self.current_layer.append(object)

    def error(self, msg):
        inkex.errormsg(msg)

    def get_original(self):
        src_attrib = Converter.inktex_src_namespace
        for i in self.options.ids:
            node = self.selected[i]

            if node.tag != Converter.svg_g_namespace:
                continue

            if src_attrib in node.attrib:
                return node, node.attrib.get(src_attrib, '').decode(
                    'string-escape')

        return None, None


if __name__ == "__main__":
    it = InkTex()
    it.affect()