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
import Org
import conf
import WebView
import utils


class BugsListWidget (gtk.TreeView):
    def __init__ (self):
        self.sql = None
        self.sql_result = None
        self.email = conf.USER

        # Widget
        self.treestore = gtk.TreeStore (str, str, str)

        gtk.TreeView.__init__ (self, self.treestore)
        self.__build_widget()

    def deselect_all (self):
        treeselection = self.get_selection()
        treeselection.unselect_all()

    def set_user (self, email):
        self.email = email
        self.sql = None
        self.sql_result = None

        self._refresh()
        self._redraw_list()

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

    def _refresh (self):
        sql = self._get_sql()
        self.sql_result = DB.fetchall_cacheable (sql)
        return True

    def _redraw_list (self):
        # Empty the TreeStore
        self.treestore.clear()

        # Add bugs
        for row in self.sql_result:
            self.treestore.append (None, [row['bug_id'], row['short_desc'], row['bug_status']])


class MyTasksListWidget (BugsListWidget):
    def __init__ (self):
        BugsListWidget.__init__ (self)

    def _get_sql (self):
        user_id = Bugs.get_user_id(self.email)
        product_id = Bugs.get_product_id()
        return "select * from BugzillaS.bugs bugs where bugs.assigned_to = %s and bugs.product_id = %s and bugs.bug_status != 'CLOSED'" %(user_id, product_id)


class MyBugsListWidget (BugsListWidget):
    def __init__ (self):
        BugsListWidget.__init__ (self)

    def _get_sql (self):
        user_id = Bugs.get_user_id(self.email)
        product_id = Bugs.get_product_id()
        return "select * from BugzillaS.bugs bugs where bugs.assigned_to = %s and bugs.product_id != %s and bugs.bug_status != 'CLOSED'" %(user_id, product_id)


class BugDetails (gtk.VBox):
    def __init__ (self):
        gtk.VBox.__init__ (self)
        self.webview_progress = WebView.Widget_Progress()
        self.pack_start (self.webview_progress)

    def load_bug (self, bug_id):
        assert str(bug_id).isdigit()

        bug_url = conf.BUGZILLA_URL + '/show_bug.cgi?id=%s' %(bug_id)
        self.webview_progress.webview.open(bug_url)

    def new_bug (self, user):
        newbug_url = conf.BUGZILLA_URL + '/enter_bug.cgi?product=%s&assigned_to=%s&component=Tasks' %(conf.TASKS_PRODUCT, user)
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

    def load_user (self, email):
        self.my_list.set_user (email)


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

    def load_user (self, email):
        for n in range(self.get_n_pages()):
            page_n_widget = self.get_nth_page(n)
            page_n_widget.load_user (email)


class Combobox_Users (gtk.ComboBox):
    def __init__ (self):
        # Init widget
        liststore = gtk.ListStore(str)
        gtk.ComboBox.__init__ (self, liststore)
        cell = gtk.CellRendererText()
        self.pack_start(cell, True)
        self.add_attribute(cell, 'text', 0)
        self.set_row_separator_func (self.__is_separator, None)

        gtk.idle_add (self.__populate)

    def __populate (self):
        # Initial values
        self.people = [{'uid': conf.USER.split('@')[0], 'realname': 'Myself'}]
        self.people += ['---']
        self.people += Org.get_manager()
        self.people += ['---']
        self.people += Org.get_direct_reports()

        for user in self.people:
            if type(user) == str:
                self.append_text(user)
            else:
                self.append_text(user['realname'])

        # Active first entry
        self.set_active(0)

    def __is_separator (self, model, treeiter, data):
        value = model.get_value (treeiter, 0)
        return value == '---'

    def get_active_user (self):
        active_n = self.get_active()
        return self.people[active_n]


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

        # Users
        self.users_combobox = Combobox_Users()
        self.users_combobox.connect ('changed', self.__cb_combobox_user_changed)

        user_label = gtk.Label()
        user_label.set_markup("<b>User</b>")

        user_hbox = gtk.HBox()
        user_hbox.pack_start (user_label, fill=False, expand=False, padding=7)
        user_hbox.pack_start (self.users_combobox)

        vbox = gtk.VBox()
        vbox.pack_start (user_hbox, fill=False, expand=False)
        vbox.pack_start (gtk.HSeparator(), fill=False, expand=False, padding=7)
        vbox.pack_start (self.notebook, fill=True, expand=True)

        # Main panel
        paned = gtk.HPaned()
        paned.add1 (vbox)
        paned.add2 (bug_details_scrolled)

        self.vbox.pack_start (toolbar, fill=True, expand=False)
        self.vbox.pack_start (paned, fill=True, expand=True)

        # Initial state
        self.bug_details.new_bug(conf.USER)

    def __cb_combobox_user_changed (self, combobox):
        self.notebook.props.sensitive = False
        utils.process_events()

        user = combobox.get_active_user()
        email = '%s@redhat.com' %(user['uid'])
        self.notebook.load_user (email)
        utils.process_events()

        self.notebook.props.sensitive = True

    def __cb_delete_event(self, widget, event, data=None):
        return False

    def __cb_destroy(self, widget, data=None):
        self.hide()
        gtk.main_quit()

    def _cb_new_clicked (self, widget, *args):
        # Deselect list rows
        def deselect (lists_panel):
            lists_panel.deselect_all()

        self.notebook.foreach (deselect)

        # New bug page
        user = self.users_combobox.get_active_user()
        self.bug_details.new_bug('%s@redhat.com' % (user['uid']))


def handle_config_files():
    config_path = os.path.join (os.getenv('HOME'), ".config", "rhos-tasks")
    if not os.path.exists(config_path):
        os.makedirs (config_path, 0700)


def thread_autoupdate_func(*args):
    while True:
        # Update the queries
        DB.Memoize.refresh_all()

        # Wait a random time
        lapse_sec = random.randrange(5*60,10*60)
        time.sleep (lapse_sec)


def build_app():
    # Configuration
    handle_config_files()

    # Build the GUI
    window = MainWindow()
    window.show_all()

    # Deal with the DB cache
    DB.Memoize.load()
    atexit.register (lambda: DB.Memoize.save())

    # Launch auto-updating thread
    thread_auto = thread.start_new_thread (thread_autoupdate_func, (None,))


def run():
    build_app()
    gtk.main()
