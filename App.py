# -*- mode: python; coding: utf-8 -*-

# AUTHORS:
#  Alvaro Lopez Ortega <alvaro@redhat.com>

import os
import thread
import logging
import traceback
import atexit
import random
import time

# GTK+ imports
import pygtk
pygtk.require('2.0')
import gtk
import webkit
import gobject

# App
import DB
import Bugs
import conf
import WebView
import utils


class BugsListWidget (gtk.TreeView):
    def __init__ (self):
        self.sql = None
        self.sql_result = None

        # Widget
        self.treestore = gtk.TreeStore (str, str, str)

        gtk.TreeView.__init__ (self, self.treestore)
        self.__build_widget()

        # Refresh
        self.refresh_lapse = random.randrange(3*60,5*60)
        self.refresh_timer = gobject.timeout_add(self.refresh_lapse * 1000, self.__cb_timed_update)

    def deselect_all (self):
        treeselection = self.get_selection()
        treeselection.unselect_all()

    def __build_widget (self):
        col = 0

        self.column_name = gtk.TreeViewColumn ('Number')
        self.append_column (self.column_name)
        self.cell_name = gtk.CellRendererText()
        self.column_name.pack_start (self.cell_name, True)
        self.column_name.add_attribute (self.cell_name, 'text', col)
        self.column_name.set_sort_column_id (0)
        col += 1

        self.column_status = gtk.TreeViewColumn ('Description')
        self.append_column (self.column_status)
        self.cell_status = gtk.CellRendererText()
        self.column_status.pack_start (self.cell_status, True)
        self.column_status.add_attribute (self.cell_status, 'text', col)
        self.column_status.set_sort_column_id (1)
        col += 1

        self.column_size = gtk.TreeViewColumn ('Status')
        self.append_column (self.column_size)
        self.cell_size = gtk.CellRendererText()
        self.column_size.pack_start (self.cell_size, True)
        self.column_size.add_attribute (self.cell_size, 'text', col)
        self.column_size.set_sort_column_id (2)

    def _refresh (self, cache_invalidate):
        self.sql_result = DB.fetchall_cacheable (self.sql, cache_invalidate=cache_invalidate)
        return True

    def _redraw_list (self):
        # Empty the TreeStore
        self.treestore.clear()

        # Add bugs
        for row in self.sql_result:
            self.treestore.append (None, [row['bug_id'], row['short_desc'], row['bug_status']])

    def __cb_timed_update (self):
        prev_result = str(self.sql_result)

        self._refresh (cache_invalidate = True)

        if prev_result != str(self.sql_result):
            self._redraw_list()

        return True

class MyTasksListWidget (BugsListWidget):
    def __init__ (self):
        BugsListWidget.__init__ (self)

    def do_initial_update (self, email):
        if self.sql == None:
            user_id = Bugs.get_user_id(email)
            product_id = Bugs.get_product_id()
            self.sql = "select * from BugzillaS.bugs bugs where bugs.assigned_to = %s and bugs.product_id = %s and bugs.bug_status != 'CLOSED'" %(user_id, product_id)

        self._refresh (cache_invalidate = False)
        self._redraw_list()

class MyBugsListWidget (BugsListWidget):
    def __init__ (self):
        BugsListWidget.__init__ (self)

    def do_initial_update (self, email):
        if self.sql == None:
            user_id = Bugs.get_user_id(email)
            product_id = Bugs.get_product_id()
            self.sql = "select * from BugzillaS.bugs bugs where bugs.assigned_to = %s and bugs.product_id != %s and bugs.bug_status != 'CLOSED'" %(user_id, product_id)

        self._refresh (cache_invalidate = False)
        self._redraw_list()


class BugDetails (gtk.VBox):
    def __init__ (self):
        gtk.VBox.__init__ (self)
        self.webview_progress = WebView.Widget_Progress()
        self.pack_start (self.webview_progress)

    def load_bug (self, bug_id):
        assert str(bug_id).isdigit()

        bug_url = conf.BUGZILLA_URL + '/show_bug.cgi?id=%s' %(bug_id)
        self.webview_progress.webview.open(bug_url)

    def new_bug (self):
        newbug_url = conf.BUGZILLA_URL + '/enter_bug.cgi?product=%s&assigned_to=%s&component=Tasks' %(conf.TASKS_PRODUCT, conf.USER)
        self.webview_progress.webview.open(newbug_url)


class Toolbar (gtk.Toolbar):
    def __init__ (self):
        gtk.Toolbar.__init__ (self)

        self.set_orientation(gtk.ORIENTATION_HORIZONTAL)
        self.set_style(gtk.TOOLBAR_BOTH)
        self.set_border_width(5)


class ListPanel_Generic (gtk.VBox):
    def __init__ (self, email, bug_details_widget, list_widget_class):
        gtk.VBox.__init__ (self)
        self.bug_details = bug_details_widget

        # List
        self.my_list = list_widget_class()
        self.my_list.get_selection().connect ('changed', self.__cb_tasks_list_row_clicked)
        gtk.idle_add (self.my_list.do_initial_update, email)

        # Scroll
        my_list_scrolled = gtk.ScrolledWindow()
        my_list_scrolled.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
        my_list_scrolled.add_with_viewport(self.my_list)

        self.pack_start (my_list_scrolled, fill=True, expand=True)

    def deselect_all (self):
        self.my_list.deselect_all()

    def __cb_tasks_list_row_clicked (self, tree_selection):
        # Figure out selected bug
        (model, pathlist) = tree_selection.get_selected_rows()
        if not len(pathlist):
            return False

        tree_iter = model.get_iter(pathlist[0])
        bug_id = model.get_value(tree_iter,0)

        # Load it
        self.bug_details.load_bug(bug_id)

        # Deselect rest of the lists
        parent_notebook = self.get_parent()
        parent_notebook.deselect_all_but_widget (self)


class Notebook (gtk.Notebook):
    def __init__ (self):
        gtk.Notebook.__init__ (self)

    def deselect_all_but_widget (self, child_widget):
        for n in range(self.get_n_pages()):
            page_n_widget = self.get_nth_page(n)
            if page_n_widget == child_widget:
                continue
            if not isinstance(page_n_widget, ListPanel_Generic):
                continue
            page_n_widget.deselect_all()


class MainWindow (gtk.Window):
    TITLE = "RHOS Tasks"

    def __init__ (self):
        # Constructor
        gtk.Window.__init__ (self, gtk.WINDOW_TOPLEVEL)

        # Basic events
        self.connect("delete_event", self.__cb_delete_event)
        self.connect("destroy", self.__cb_destroy)

        # Properties
        self.maximize()
        self.set_title(self.TITLE)

        self.vbox = gtk.VBox()
        self.add (self.vbox)

        toolbar = Toolbar()
        toolbar.append_item("New", "New Task", "private", None, self._cb_new_clicked)
        toolbar.append_space()
        toolbar.append_item("Quit", "Quit App", "private", None, self.__cb_destroy)

        # Bug details
        self.bug_details = BugDetails()

        bug_details_scrolled = gtk.ScrolledWindow()
        bug_details_scrolled.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
        bug_details_scrolled.add_with_viewport(self.bug_details)

        # Tabs
        self.notebook = Notebook()
        self.notebook.set_tab_pos(gtk.POS_TOP)
        self.notebook.append_page(ListPanel_Generic (conf.USER, self.bug_details, MyTasksListWidget), gtk.Label("Tasks"))
        self.notebook.append_page(ListPanel_Generic (conf.USER, self.bug_details, MyBugsListWidget), gtk.Label("Bugs"))

        # Main panel
        paned = gtk.HPaned()
        paned.add1 (self.notebook)
        paned.add2 (bug_details_scrolled)

        self.vbox.pack_start (toolbar, fill=True, expand=False)
        self.vbox.pack_start (paned, fill=True, expand=True)

        # Initial state
        self.bug_details.new_bug()

    def __cb_delete_event(self, widget, event, data=None):
        return False

    def __cb_destroy(self, widget, data=None):
        self.hide()
        gtk.main_quit()

    def _cb_new_clicked (self, widget, *args):
        def deselect (lists_panel):
            lists_panel.deselect_all()

        self.notebook.foreach (deselect)
        self.bug_details.new_bug()


def handle_config_files():
    config_path = os.path.join (os.getenv('HOME'), ".config", "rhos-tasks")
    if not os.path.exists(config_path):
        os.makedirs (config_path, 0700)


def build_app():
    # Configuration
    handle_config_files()

    # Build the GUI
    window = MainWindow()
    window.show_all()

    # Deal with the DB cache
    DB.Memoize.load()
    atexit.register (lambda: DB.Memoize.save())


def run():
    build_app()
    gtk.main()




old = """
#       self.notebook.connect ('switch-page', self.__cb_notebook_changed)
#   def __cb_notebook_changed (self, notebook, page, page_num):
#       None
"""

old = """
class ListsPanel (gtk.VBox):
    def __init__ (self, email, bug_details_widget):
        gtk.VBox.__init__ (self)
        self.bug_details = bug_details_widget

        # Tasks
        self.my_tasks = MyTasksListWidget()
        self.my_tasks.get_selection().connect ('changed', self.__cb_tasks_list_row_clicked)
        gtk.idle_add (self.my_tasks.do_initial_update, email)

        my_tasks_scrolled = gtk.ScrolledWindow()
        my_tasks_scrolled.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
        my_tasks_scrolled.add_with_viewport(self.my_tasks)

        my_tasks_label = gtk.Label()
        my_tasks_label.set_justify (gtk.JUSTIFY_LEFT)
        my_tasks_label.set_markup ('<b>My Tasks</b>')

        # Bugs
        self.my_bugs = MyBugsListWidget()
        self.my_bugs.get_selection().connect ('changed', self.__cb_bugs_list_row_clicked)
        gtk.idle_add (self.my_bugs.do_initial_update, email)

        my_bugs_scrolled = gtk.ScrolledWindow()
        my_bugs_scrolled.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
        my_bugs_scrolled.add_with_viewport(self.my_bugs)

        my_bugs_label = gtk.Label()
        my_bugs_label.set_justify (gtk.JUSTIFY_LEFT)
        my_bugs_label.set_markup ('<b>My Bugs</b>')

        # Left panel
        mytasks_vbox = gtk.VBox()
        mytasks_vbox.pack_start (my_tasks_label, fill=True, expand=False)
        mytasks_vbox.pack_start (my_tasks_scrolled, fill=True, expand=True)

        mybugs_vbox = gtk.VBox()
        mybugs_vbox.pack_start (my_bugs_label, fill=True, expand=False)
        mybugs_vbox.pack_start (my_bugs_scrolled, fill=True, expand=True)

        left = gtk.VPaned()
        left.add1(mytasks_vbox)
        left.add2(mybugs_vbox)

        self.pack_start (left, fill=True, expand=True)

    def deselect_all (self):
        self.my_bugs.deselect_all()
        self.my_tasks.deselect_all()

    def __handle_row_clicked (self, tree_selection):
        (model, pathlist) = tree_selection.get_selected_rows()
        if not len(pathlist):
            return False

        tree_iter = model.get_iter(pathlist[0])
        bug_id = model.get_value(tree_iter,0)

        # Load it
        self.bug_details.load_bug(bug_id)

    def __cb_bugs_list_row_clicked (self, tree_selection):
        re = self.__handle_row_clicked (tree_selection)
        if re == False:
            return
        self.my_tasks.deselect_all()

    def __cb_tasks_list_row_clicked (self, tree_selection):
        re = self.__handle_row_clicked (tree_selection)
        if re == False:
            return
        self.my_bugs.deselect_all()
"""


old = """


#        self.my_tasks.connect ('button-press-event', self.__cb_list_row_clicked)
#        self.my_bugs.connect ('button-press-event', self.__cb_list_row_clicked)

#    def __cb_list_row_clicked (self, widget, event):
        # Only attend to double-click
#        if event.type != gtk.gdk.BUTTON_PRESS:
#            return

        # Figure out the row
        tmp = widget.get_path_at_pos (int(event.x), int(event.y))
        row_num = tmp[0][0]

        model = widget.get_model()
        row = model.iter_nth_child(None, row_num)
        bug_id = model.get_value (row, 0)

        # Load it
        self.bug_details.load_bug(bug_id)
"""

old = """
class NewBugWindow (gtk.Window):
    TITLE = "New Task"

    def __init__ (self):
        gtk.Window.__init__ (self)

        self.set_title (self.TITLE)
        self.resize (1000,820)

        newbug_url = conf.BUGZILLA_URL + '/enter_bug.cgi?product=%s' %(conf.TASKS_PRODUCT)

        webprogress = WebView.Widget_Progress()
        webprogress.webview.open(newbug_url)

        self.add (webprogress)
"""

old = """
class WebViewProgress (gtk.VBox):
    def __init__ (self):
        gtk.VBox.__init__ (self)

        # Progress bar
        self.progressBar = gtk.ProgressBar()
        self.progressBar.set_size_request(150, -1)

        # WebView
        self.webview = webkit.WebView()
        self.webview.connect('load-progress-changed', self.__cb_progress_changed)
        self.webview.connect('load-started', self.__cb_progress_started)
        self.webview.connect('load-finished', self.__cb_progress_finished)

        # WebView's scrolled
        scrolled = gtk.ScrolledWindow()
        scrolled.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        scrolled.add_with_viewport(self.webview)

        # Pack it up
        self.pack_start (self.progressBar, fill=True, expand=False)
        self.pack_start (scrolled, fill=True, expand=True)

    def __cb_progress_changed(self, web_view, amount):
        self.progressBar.set_fraction(amount / 100.0)

    def __cb_progress_started(self, web_view, frame):
        self.progressBar.show()

    def __cb_progress_finished(self, web_view, frame):
        self.progressBar.hide()
"""

old ="""
class NewBugWindow (gtk.Window):
    TITLE = "New Task"
    html_cache = None

    def __init__ (self):
        gtk.Window.__init__ (self)

        self.html_cache = None
        self.set_title (self.TITLE)
        self.webview = webkit.WebView()

        self.webview.connect('document-load-finished', self.__cb_load_finished)
        self.webview.connect('load-progress-changed', self.__cb_progress_changed)
        self.webview.connect('load-started', self.__cb_progress_started)
        self.webview.connect('load-finished', self.__cb_progress_finished)

        self.progressBar = gtk.ProgressBar()
        self.progressBar.set_size_request(150, -1)

        scrolled = gtk.ScrolledWindow()
        scrolled.set_policy (gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        scrolled.add_with_viewport(self.webview)

        vbox = gtk.VBox()
        vbox.pack_start (self.progressBar, fill=True, expand=False)
        vbox.pack_start (scrolled, fill=True, expand=True)

        self.add (vbox)
        self.resize (1000,820)

        if not NewBugWindow.html_cache:
            print "Carga"
            self.webview.load_html_string('<h1 style="text-align: center"><br/><br/>Loading...</h1>', "file:///")
            utils.process_events()

            newbug_url = conf.BUGZILLA_URL + '/enter_bug.cgi?product=%s' %(conf.TASKS_PRODUCT)
            self.webview.open(newbug_url)
        else:
            print "cache"
            self.webview.load_html_string(NewBugWindow.html_cache, "file:///")

    def __get_html(self):
        self.webview.execute_script('oldtitle=document.title;document.title=document.documentElement.innerHTML;')
        html = self.webview.get_main_frame().get_title()
        self.webview.execute_script('document.title=oldtitle;')
        return html

    def __cb_progress_changed(self, web_view, amount):
        self.progressBar.set_fraction(amount / 100.0)

    def __cb_progress_started(self, web_view, frame):
            self.progressBar.show()

    def __cb_progress_finished(self, web_view, frame):
        self.progressBar.hide()

    def __cb_load_finished (self, view, frame):
        return

        if self.html_cache:
            return

        html = self.__get_html()

        header_pos = html.find ('<div id="header">')
        body_pos   = html.find ('<div id="bugzilla-body">')

        print "header_pos", header_pos
        print "body_pos", body_pos

        if header_pos != -1 and body_pos != -1:
            self.webview.load_html_string("<script>alert('hola');</script>", "file:///")
            return



            clean_html = html[:header_pos]
            clean_html += html[body_pos:]

            print html[:header_pos]
            print "-"*70
            print html[header_pos:body_pos]
            print "-"*70
            print html[body_pos:]

            NewBugWindow.html_cache = clean_html
            self.webview.load_html_string(clean_html, "file:///")
"""
