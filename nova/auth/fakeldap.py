import logging
from nova import datastore

KEEPER = datastore.keeper('fakeldap')

SCOPE_SUBTREE  = 1

class NO_SUCH_OBJECT(Exception):
    pass

def initialize(uri):
    return FakeLDAP(uri)

if KEEPER['objects'] is None:
    KEEPER['objects'] = {}

class FakeLDAP(object):
    def __init__(self, uri):
        self.uri = uri

    def simple_bind_s(self, dn, password):
        pass
    
    def unbind_s(self):
        pass

    def search_s(self, dn, scope, query=None, fields=None):
        logging.debug("searching for %s" % dn)
        filtered = {}
        d = KEEPER['objects']
        for cn, attrs in d.iteritems():
            if cn[-len(dn):] == dn:
                filtered[cn] = attrs
        if query:
            k,v = query[1:-1].split('=')
            objects = {}
            for cn, attrs in filtered.iteritems():
                if attrs.has_key(k) and (v in attrs[k] or
                    v == attrs[k]):
                    objects[cn] = attrs
        if objects == {}:
            raise NO_SUCH_OBJECT()
        return objects.items()
    
    def add_s(self, cn, attr):
        logging.debug("adding %s" % cn)
        stored = {}
        for k, v in attr:
            if type(v) is list:
                stored[k] = v
            else:
                stored[k] = [v]
        d = KEEPER['objects']
        d[cn] = stored
        KEEPER['objects'] = d

    def delete_s(self, cn):
        logging.debug("creating for %s" % cn)
        d = KEEPER['objects']
        del d[cn]
        KEEPER['objects'] = d
