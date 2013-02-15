# -*- mode: python; coding: utf-8 -*-

# AUTHORS:
#  Alvaro Lopez Ortega <alvaro@redhat.com>

import DB
import conf


@DB.Memoize
def get_user_id(username = conf.USER):
    SQL = "select userid from BugzillaS.profiles profiles where profiles.login_name = '%s'" %(username)
    return DB.fetchall(SQL)[0]['userid']

@DB.Memoize
def get_product_id(product = conf.TASKS_PRODUCT):
    SQL = "select id from BugzillaS.products products where products.name = '%s'" %(product)
    return DB.fetchall(SQL)[0]['id']


if __name__ == "__main__":
    print "%s, ID=%s" %(conf.USER, get_user_id())
    print "%s, ID=%s" %(conf.TASKS_PRODUCT, get_product_id())
