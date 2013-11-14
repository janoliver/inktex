import os

import pygtk
pygtk.require('2.0')
import gtk

from gtkcodebuffer import CodeBuffer, SyntaxLoader


class Ui(object):
    """
    The user interface. This dialog is the LaTeX input window and includes
    widgets to display compilation logs and a preview. It uses GTK2 which
    must be installed an importable.
    """

    app_name = 'InkTeX'

    help_text = r"""You can set a preamble file and scale factor in the <b>settings</b> tab. The preamble should not include <b>\documentclass</b> and <b>\begin{document}</b>.

The LaTeX code you write is only the stuff between <b>\begin{document}</b> and <b>\end{document}</b>. Compilation errors are reported in the <b>log</b> tab.

The preamble file and scale factor are stored on a per-drawing basis, so in a new document, these information must be set again."""

    about_text = r"""Written by <a href="mailto:janoliver@oelerich.org">Jan Oliver Oelerich &lt;janoliver@oelerich.org&gt;</a>"""

    def __init__(self, render_callback, src, settings):
        """Takes the following parameters:
          * render_callback: callback function to execute with "apply" button
          * src: source code that should be pre-inserted into the LaTeX input"""

        self.render_callback = render_callback
        self.src = src if src else ""
        self.settings = settings

        # init the syntax highlighting buffer
        lang = SyntaxLoader("latex")
        self.syntax_buffer = CodeBuffer(lang=lang)

        self.setup_ui()

    def render(self, widget, data=None):
        """Extracts the input LaTeX code and calls the render callback. If that
        returns true, we quit and are happy."""

        buf = self.text.get_buffer()
        tex = buf.get_text(buf.get_start_iter(), buf.get_end_iter())

        settings = dict()
        if self.preamble.get_filename():
            settings['preamble'] = self.preamble.get_filename()
        settings['scale'] = self.scale.get_value()

        if self.render_callback(tex, settings):
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
        self.page_latex = gtk.HBox(False, 5)
        self.page_latex.set_border_width(8)
        self.page_latex.show()
        self.page_log = gtk.HBox(False, 5)
        self.page_log.set_border_width(8)
        self.page_log.show()
        self.page_settings = gtk.HBox(False, 5)
        self.page_settings.set_border_width(8)
        self.page_settings.show()
        self.page_help = gtk.VBox(False, 5)
        self.page_help.set_border_width(8)
        self.page_help.show()
        self.notebook.append_page(self.page_latex, gtk.Label("LaTeX"))
        self.notebook.append_page(self.page_log, gtk.Label("Log"))
        self.notebook.append_page(self.page_settings, gtk.Label("Settings"))
        self.notebook.append_page(self.page_help, gtk.Label("Help"))
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

        self.page_latex.pack_start(self.text_container)


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

        self.page_log.pack_start(self.log_container)


        # third component: settings
        self.settings_container = gtk.Table(2,2)
        self.settings_container.set_row_spacings(8)
        self.settings_container.show()

        self.label_preamble = gtk.Label("Preamble")
        self.label_preamble.set_alignment(0, 0.5)
        self.label_preamble.show()
        self.preamble = gtk.FileChooserButton("...")
        if 'preamble' in self.settings and os.path.exists(self.settings['preamble']):
            self.preamble.set_filename(self.settings['preamble'])
        self.preamble.set_action(gtk.FILE_CHOOSER_ACTION_OPEN)
        self.preamble.show()
        self.settings_container.attach(self.label_preamble, yoptions=gtk.SHRINK,
            left_attach=0, right_attach=1, top_attach=0, bottom_attach=1)
        self.settings_container.attach(self.preamble, yoptions=gtk.SHRINK,
            left_attach=1, right_attach=2, top_attach=0, bottom_attach=1)

        self.label_scale = gtk.Label("Scale")
        self.label_scale.set_alignment(0, 0.5)
        self.label_scale.show()
        self.scale_adjustment = gtk.Adjustment(value=1.0, lower=0, upper=100,
                                               step_incr=0.1)
        self.scale = gtk.SpinButton(adjustment=self.scale_adjustment, digits=1)
        if 'scale' in self.settings:
            self.scale.set_value(float(self.settings['scale']))
        self.scale.show()
        self.settings_container.attach(self.label_scale, yoptions=gtk.SHRINK,
            left_attach=0, right_attach=1, top_attach=1, bottom_attach=2)
        self.settings_container.attach(self.scale, yoptions=gtk.SHRINK,
            left_attach=1, right_attach=2, top_attach=1, bottom_attach=2)

        self.page_settings.pack_start(self.settings_container)


        # help tab
        self.help_label = gtk.Label()
        self.help_label.set_markup(Ui.help_text)
        self.help_label.set_line_wrap(True)
        self.help_label.show()

        self.about_label = gtk.Label()
        self.about_label.set_markup(Ui.about_text)
        self.about_label.set_line_wrap(True)
        self.about_label.show()

        self.separator_help = gtk.HSeparator()
        self.separator_help.show()

        self.page_help.pack_start(self.help_label)
        self.page_help.pack_start(self.separator_help)
        self.page_help.pack_start(self.about_label)


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

