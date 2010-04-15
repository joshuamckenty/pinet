# vim: tabstop=4 shiftwidth=4 softtabstop=4
import logging

class Error(Exception):
    pass

class ApiError(Error): 
    def __init__(self, message, code='Unknown'):
        self.message = message
        self.code = code

def wrap_exception(f):
    def _wrap(*args, **kw):
        try:
            return f(*args, **kw)
        except Exception, e:
            if not isinstance(e, Error):
                logging.exception('Uncaught exception')
                raise Error(str(e))
            raise
    _wrap.func_name = f.func_name
    return _wrap
        

