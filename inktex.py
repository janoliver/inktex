#!/usr/bin/env python2

import tempfile
import os
import subprocess
import shutil
import copy
import time
import re

import inkex

import pygtk

pygtk.require('2.0')
import gtk

class Ui(object):
    def __init__(self, render_callback, src):
        self.render_callback = render_callback
        self.src = src if src else ""
        self.setup_ui()

    def render(self, widget, data=None):
        buf = self.text.get_buffer()
        tex = buf.get_text(buf.get_start_iter(), buf.get_end_iter())
        if self.render_callback(tex):
            gtk.main_quit()
            return False

    def cancel(self, widget, data=None):
        raise SystemExit(1)

    def destroy(self, widget, event, data=None):
        gtk.main_quit()
        return False

    def setup_ui(self):
        self.window = gtk.Window(gtk.WINDOW_TOPLEVEL)
        self.window.set_type_hint(gtk.gdk.WINDOW_TYPE_HINT_DIALOG)
        self.window.set_title("InkTex")

        # Window destroy event
        self.window.connect("destroy", self.destroy)

        # create gui
        self.window.set_border_width(8)

        self.box_container = gtk.VBox(False, 5)
        self.window.add(self.box_container)

        self.text = gtk.TextView()
        self.text.get_buffer().set_text(self.src)

        self.text_container = gtk.ScrolledWindow()
        self.text_container.set_policy(gtk.POLICY_AUTOMATIC,
                                       gtk.POLICY_AUTOMATIC)
        self.text_container.set_shadow_type(gtk.SHADOW_IN)
        self.text_container.add(self.text)
        self.text.show()
        self.text_container.set_size_request(400, 200)
        self.text_container.show()
        self.box_container.pack_start(self.text_container, True, True)

        self.separator_buttons = gtk.HSeparator()
        self.separator_buttons.show()
        self.box_container.pack_start(self.separator_buttons, False, False)

        # the buttons box
        self.box_buttons = gtk.HButtonBox()
        self.box_buttons.set_layout(gtk.BUTTONBOX_END)

        self.box_container.pack_start(self.box_buttons, False, False)

        # our two buttons
        self.button_render = gtk.Button("Apply", stock=gtk.STOCK_APPLY)
        self.button_render.set_flags(gtk.CAN_DEFAULT)
        self.button_cancel = gtk.Button("Close", stock=gtk.STOCK_CLOSE)
        self.button_render.connect("clicked", self.render, None)
        self.button_cancel.connect("clicked", self.cancel, None)
        self.box_buttons.pack_end(self.button_cancel)
        self.box_buttons.pack_end(self.button_render)
        self.button_render.show()
        self.button_cancel.show()

        # and the window
        self.box_buttons.show()
        self.box_container.show()
        self.window.connect("delete-event", self.destroy)
        self.window.set_default(self.button_render)
        self.window.show()

    def main(self):
        gtk.main()


class CompilerException(Exception):
    pass


class ConverterException(Exception):
    pass


class Converter(object):
    skeleton = r"""\documentclass{article}
                \begin{document}
                \pagestyle{empty}
                \noindent
                    %s
                \end{document}"""

    tex_file = 'inktex.tex'
    pdf_file = 'inktex.pdf'
    svg_file = 'inktex.svg'

    inktex_namespace = u'http://www.oelerich.org/inktex'
    svg_namespace = u'http://www.w3.org/2000/svg'
    xlink_namespace = u'http://www.w3.org/1999/xlink'

    namespaces = {
        u'inktex': inktex_namespace,
        u'svg': svg_namespace,
        u'xlink': xlink_namespace,
    }

    compiler = 'pdflatex'
    converter = 'pdf2svg'

    def __enter__(self):
        self.tmp_dir = tempfile.mkdtemp()
        return self

    def __exit__(self, type, value, traceback):
        shutil.rmtree(self.tmp_dir)

    def write_latex(self, tex_code):
        f = open(os.path.join(self.tmp_dir, self.tex_file), 'a')
        f.write(self.skeleton % tex_code)
        f.close()

    def compile(self):
        proc_latex = subprocess.Popen(
            [self.compiler, self.tex_file], cwd=self.tmp_dir,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            stdin=subprocess.PIPE
        )

        latex_out, latex_err = proc_latex.communicate()

        if proc_latex.returncode:
            raise CompilerException(latex_err)

        proc_pdf2svg = subprocess.Popen(
            [self.converter, self.pdf_file, self.svg_file], cwd=self.tmp_dir,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            stdin=subprocess.PIPE
        )

        pdf2svg_out, pdf2svg_err = proc_pdf2svg.communicate()

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
        master_group.attrib['{%s}src' % self.inktex_namespace] = tex.encode(
            'string-escape')

        return copy.copy(master_group)

    def scramble_ids(self, root):
        href_map = dict()

        # Map items to new ids
        for i, el in enumerate(root.xpath('//*[attribute::id]')):
            cur_id = el.attrib['id']
            new_id = '%s-%s' % (time.time(), i)
            href_map['#' + cur_id] = "#" + new_id
            el.attrib['id'] = new_id

        # Replace hrefs
        url_re = re.compile('^url\((.*)\)$')

        for el in root.xpath('//*[attribute::xlink:href]', namespaces=self.namespaces):
            cur_href = el.attrib['{%s}href' % self.xlink_namespace]
            el.attrib['{%s}href' % self.xlink_namespace] = href_map.get(cur_href, cur_href)

        for el in root.xpath('//*[attribute::svg:clip-path]', namespaces=self.namespaces):
            m = url_re.match(el.attrib['clip-path'])
            if m:
                el.attrib['clip-path'] = \
                    'url(%s)' % href_map.get(m.group(1), m.group(1))


class InkTex(inkex.Effect):

    def __init__(self):
        inkex.Effect.__init__(self)
        self.orig = None

    def effect(self):
        self.orig, src = self.get_original()

        self.ui = Ui(self.render, src)
        self.ui.main()

    def render(self, tex):
        with Converter() as renderer:
            try:
                renderer.write_latex(tex)
                renderer.compile()
                svg_tree = renderer.get_svg_group(tex)
                self.copy_styles(svg_tree)
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
        src_attrib = '{%s}src' % Converter.inktex_namespace
        for i in self.options.ids:
            node = self.selected[i]

            if node.tag != '{%s}g' % Converter.svg_namespace:
                continue

            if src_attrib in node.attrib:
                return node, node.attrib.get(src_attrib, '').decode(
                    'string-escape')

        return None, None

    def copy_styles(self, svg_tree):
        if self.orig is None:
            return

        if 'transform' in self.orig.attrib:
            svg_tree.attrib['transform'] = self.orig.attrib['transform']

        if '{%s}transform' % Converter.svg_namespace in self.orig.attrib:
            svg_tree.attrib['transform'] = self.orig.attrib['{%s}transform' % Converter.svg_namespace]

        if 'style' in self.orig.attrib:
            svg_tree.attrib['style'] = self.orig.attrib['style']



if __name__ == "__main__":
    it = InkTex()
    it.affect()