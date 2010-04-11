SCOPE_SUBTREE  = 1

class NO_SUCH_OBJECT(Exception):
    pass

def initialize(uri):
    return FakeLDAP(uri)

_users = {}

class FakeLDAP(object):
    def __init__(self, uri):
        self.uri = uri

    def simple_bind_s(self, dn, password):
        pass
    
    def unbind_s(self):
        pass

    def search_s(self, cn, scope, query=None, fields=None):
        print "searching for %s" % cn
        try:
            if fields:
                k,v = query[1:-1].split('=')
                for cn, attrs in _users.iteritems():
                    if dict(attrs)[k] == v:
                        user = attrs
            else:
                user = _users[cn]
            attrs = {}
            for k,v in user[1:]:
                attrs[k] = [v]
            return [[cn, attrs]]
        except Exception:
            raise NO_SUCH_OBJECT()
    
    def add_s(self, cn, attr):
        print "adding %s" % cn
        _users[cn] = attr

    def delete_s(self, cn):
        del _users[cn]
    
