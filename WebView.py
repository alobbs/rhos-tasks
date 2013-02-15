# -*- mode: python; coding: utf-8 -*-

# AUTHORS:
#  Alvaro Lopez Ortega <alvaro@redhat.com>

import os
import ctypes
import logging

# GTK+ imports
import pygtk
pygtk.require('2.0')
import gtk

# WebKit
import webkit

libgobject = ctypes.CDLL('/lib64/libgobject-2.0.so.0')
libsoup    = ctypes.CDLL('/lib64/libsoup-2.4.so.1')
libwebkit  = ctypes.CDLL('/lib64/libwebkitgtk-1.0.so.0')

class Widget (webkit.WebView):
    def __init__ (self, *args, **kws):
        webkit.WebView.__init__ (self, *args, **kws)
        self.__set_cookie_jar()

    def __set_cookie_jar (self):
        cookies_path = os.path.join (os.getenv('HOME'), ".config", "rhos-tasks", "cookies")

        # WebKit Session
        session = libwebkit.webkit_get_default_session()
        logging.info ("WebKit session: 0x%x" %(session))

        # Set the Cookie jar
        cookiejar = libsoup.soup_cookie_jar_text_new(cookies_path, False)
        libsoup.soup_session_add_feature(session, cookiejar)


class Widget_Progress (gtk.VBox):
    def __init__ (self):
        gtk.VBox.__init__ (self)

        # Progress bar
        self.progressBar = gtk.ProgressBar()
        self.progressBar.set_size_request(150, -1)

        # WebView
        self.webview = Widget()
        self.webview.connect('load-progress-changed', self.__cb_progress_changed)
        self.webview.connect('load-started', self.__cb_progress_started)
        self.webview.connect('load-finished', self.__cb_progress_finished)

        # WebView's scrolled
        scrolled = gtk.ScrolledWindow()
        scrolled.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_NEVER)
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
        self.progressBar.set_fraction(0)
