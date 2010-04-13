import logging

SCOPE_SUBTREE  = 1

class NO_SUCH_OBJECT(Exception):
    pass

def initialize(uri):
    return FakeLDAP(uri)

_objects = {}

class FakeLDAP(object):
    def __init__(self, uri):
        self.uri = uri

    def simple_bind_s(self, dn, password):
        pass
    
    def unbind_s(self):
        pass

    def search_s(self, dn, scope, query=None, fields=None):
        logging.debug("searching for %s" % dn)
        try:
            filtered = {}
            for cn, attrs in _objects.iteritems():
                if cn[-len(dn):] == dn:
                    filtered[cn] = attrs
            print query
            if query:
                k,v = query[1:-1].split('=')
                objects = {}
                for cn, attrs in filtered.iteritems():
                    if v in attrs[k] or v == attrs[k]:
                        objects[cn] = attrs
            if objects == {}:
                raise NO_SUCH_OBJECT()
            print objects.items()
            return objects.items()
        except Exception:
            raise NO_SUCH_OBJECT()
    
    def add_s(self, cn, attr):
        logging.debug("adding %s" % cn)
        stored = {}
        for k, v in attr:
            stored[k] = [v]
        _objects[cn] = stored

    def delete_s(self, cn):
        logging.debug("creating for %s" % cn)
        del _objects[cn]
