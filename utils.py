# -*- mode: python; coding: utf-8 -*-

# AUTHORS:
#  Alvaro Lopez Ortega <alvaro@redhat.com>

import pygtk
pygtk.require('2.0')
import gtk

def process_events():
    while gtk.events_pending():
        gtk.main_iteration(False)
