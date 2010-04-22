import logging
import hashlib
import hmac
import urllib
import base64

_log = logging.getLogger('signer')
logging.getLogger('signer').setLevel(logging.WARN)

class Signer(object):
    """ hacked up code from boto/connection.py """
    
    def __init__(self, secret_key):
        self.hmac = hmac.new(secret_key, digestmod=hashlib.sha1)
        if hashlib.sha256:
            self.hmac_256 = hmac.new(secret_key, digestmod=hashlib.sha256)

    def generate(self, params, verb, server_string, path):
        if params['SignatureVersion'] == '0':
            t = self._calc_signature_0(params)
        elif params['SignatureVersion'] == '1':
            t = self._calc_signature_1(params)
        elif params['SignatureVersion'] == '2':
            t = self._calc_signature_2(params, verb, server_string, path)
        else:
            raise LdapUserException('Unknown Signature Version: %s' % self.SignatureVersion)
        return t
        
    def _get_utf8_value(self, value):
        if not isinstance(value, str) and not isinstance(value, unicode):
            value = str(value)
        if isinstance(value, unicode):
            return value.encode('utf-8')
        else:
            return value

    def _calc_signature_0(self, params):
        s = params['Action'] + params['Timestamp']
        self.hmac.update(s)
        keys = params.keys()
        keys.sort(cmp = lambda x, y: cmp(x.lower(), y.lower()))
        pairs = []
        for key in keys:
            val = self._get_utf8_value(params[key])
            pairs.append(key + '=' + urllib.quote(val))
        return base64.b64encode(self.hmac.digest())

    def _calc_signature_1(self, params):
        keys = params.keys()
        keys.sort(cmp = lambda x, y: cmp(x.lower(), y.lower()))
        pairs = []
        for key in keys:
            self.hmac.update(key)
            val = self._get_utf8_value(params[key])
            self.hmac.update(val)
            pairs.append(key + '=' + urllib.quote(val))
        return base64.b64encode(self.hmac.digest())

    def _calc_signature_2(self, params, verb, server_string, path):
        _log.debug('using _calc_signature_2')
        string_to_sign = '%s\n%s\n%s\n' % (verb, server_string, path)
        if self.hmac_256:
            hmac = self.hmac_256
            params['SignatureMethod'] = 'HmacSHA256'
        else:
            hmac = self.hmac
            params['SignatureMethod'] = 'HmacSHA1'
        keys = params.keys()
        keys.sort()
        pairs = []
        for key in keys:
            val = self._get_utf8_value(params[key])
            pairs.append(urllib.quote(key, safe='') + '=' + urllib.quote(val, safe='-_~'))
        qs = '&'.join(pairs)
        _log.debug('query string: %s' % qs)
        string_to_sign += qs
        _log.debug('string_to_sign: %s' % string_to_sign)
        hmac.update(string_to_sign)
        b64 = base64.b64encode(hmac.digest())
        _log.debug('len(b64)=%d' % len(b64))
        _log.debug('base64 encoded digest: %s' % b64)
        return b64

if __name__ == '__main__':
    print Signer('foo').generate({"SignatureMethod": 'HmacSHA256', 'SignatureVersion': '2'}, "get", "server", "/foo")
