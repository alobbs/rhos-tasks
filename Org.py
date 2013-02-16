# -*- mode: python; coding: utf-8 -*-

# AUTHORS:
#  Alvaro Lopez Ortega <alvaro@redhat.com>

import DB
import conf

@DB.Memoize
def get_org_id(mail = conf.USER):
    username = mail.split('@')[0]
    SQL = "select id from \"OrgChart2S.User\" u where u.Uid = '%s'" %(username)
    return DB.fetchall(SQL)[0]['id']

@DB.Memoize
def get_direct_reports(mail = conf.USER):
    manager_id = get_org_id()
    SQL = "select uid,realname from \"OrgChart2S.User\" u where u.Manager = '%s'" %(manager_id)
    return DB.fetchall(SQL)

@DB.Memoize
def get_manager(mail = conf.USER):
    username = mail.split('@')[0]
    SQL = "select uid,realname from \"OrgChart2S.User\" u where u.id = ( select Manager from \"OrgChart2S.User\" u where u.Uid = '%s' )" %(username)
    return DB.fetchall(SQL)


if __name__ == "__main__":
    print "%s, ID=%s" %(conf.USER, get_org_id())
    print "  - reports%s" %([u['uid'] for u in get_direct_reports()])
