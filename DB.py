import os
import pickle
import logging

import psycopg2
import psycopg2.extras

import utils

class Memoize:
    __cache = {}
    __cache_path = None

    def __init__ (self, f):
        self.f = f

        if not Memoize.__cache_path:
            Memoize.__cache_path = os.path.join (os.getenv('HOME'), ".config", "rhos-tasks", "db_cache.pickle")

    def __call__ (self, *args, **kwargs):
        # Special keywords
        cache_invalidate = kwargs.pop('cache_invalidate', None)

        # Cache key
        key = '%s_%s_%s' %(self.f.__name__, str(args), str(kwargs))

        if not cache_invalidate:
            # Cache
            if key in self.__cache:
                return self.__cache[key]

        # Not Cached
        tmp = self.f(*args, **kwargs)
        Memoize.__cache[key] = tmp
        return tmp

    @staticmethod
    def load():
        if os.path.exists (Memoize.__cache_path):
            Memoize.__cache = pickle.load (open(Memoize.__cache_path, 'r'))
            logging.info ("Preloaded %d entries" % (len(Memoize.__cache)))

    @staticmethod
    def save():
        if Memoize.__cache:
            pickle.dump (Memoize.__cache, open(Memoize.__cache_path, 'w+'), -1)
            logging.info ("Writing %d entries" % (len(Memoize.__cache)))


def get_cursor():
    utils.process_events()
    conn = psycopg2.connect ("dbname=EngVDBF user=teiid password=teiid host=vdb.engineering.redhat.com port=35432")
    utils.process_events()

    return conn.cursor (cursor_factory=psycopg2.extras.RealDictCursor)


def fetchall(sql):
    assert sql

    cursor = get_cursor()
    cursor.execute (sql)
    utils.process_events()

    re = cursor.fetchall()
    utils.process_events()

    return re

@Memoize
def fetchall_cacheable (*args, **kw):
    return fetchall (*args, **kw)
