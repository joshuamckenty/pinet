import logging
import random
import re
from xml.dom import minidom

from twisted.internet import defer


_c2u = re.compile('(((?<=[a-z])[A-Z])|([A-Z](?![A-Z]|$)))')
def _camelcase_to_underscore(str):
    return _c2u.sub(r'_\1', str).lower().strip('_')

def _underscore_to_camelcase(str):
    return ''.join([x[:1].upper() + x[1:] for x in str.split('_')])

def _underscore_to_xmlcase(str):
    res = _underscore_to_camelcase(str)
    return res[:1].lower() + res[1:]

class APIRequestContext(object):
    def __init__(self, user):
        self.user = user
        self.request_id = ''.join([random.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890-') for x in xrange(20)])

class APIRequest(object):
    def __init__(self, controller, action):
        self.controller = controller
        self.action = action
        
    def send(self, user, **kwargs):
        context = APIRequestContext(user)
    
        try:
            method = getattr(self.controller, _camelcase_to_underscore(self.action))
        except AttributeError:
            _error = 'Unsupported API request: controller = %s, action = %s' % (self.controller, self.action)
            logging.warning(_error)
            # TODO: Raise custom exception, trap in apiserver, reraise as 400 error.
            raise Exception(_error)
        
        args = {}
        for key, value in kwargs.items():
            parts = key.split(".")
            key = _camelcase_to_underscore(parts[0])
            if len(parts) > 1:
                d = args.get(key, {})
                d[parts[1]] = value[0]
                value = d
            else:
                value = value[0]
            args[key] = value
            
        for key in args.keys():
            if isinstance(args[key], dict):
                if args[key] != {} and args[key].keys()[0].isdigit():
                    s = args[key].items()
                    s.sort()
                    args[key] = [v for k, v in s]
        d = defer.maybeDeferred(method,
                                context, 
                                **args)
        d.addCallback(self._render_response, context.request_id)
        
        return d

    def _render_response(self, response_data, request_id):
        xml = minidom.Document()
    
        response_el = xml.createElement(self.action + 'Response')
        response_el.setAttribute('xmlns', 'http://ec2.amazonaws.com/doc/2009-11-30/')
    
        request_id_el = xml.createElement('requestId')
        request_id_el.appendChild(xml.createTextNode(request_id))
        response_el.appendChild(request_id_el)
        if(response_data == True):
            self._render_dict(xml, response_el, {'return': 'true'})
        else: 
            self._render_dict(xml, response_el, response_data)
    
        xml.appendChild(response_el)
    
        response = xml.toxml()
        xml.unlink()

        logging.debug(response)

        return response
    
    def _render_dict(self, xml, el, data):
        try:
            for key in data.keys():
                val = data[key]
                el.appendChild(self._render_data(xml, key, val))
        except:
            logging.debug(data)
            raise

    def _render_data(self, xml, el_name, data):
        el_name = _underscore_to_xmlcase(el_name)
        data_el = xml.createElement(el_name)
    
        if isinstance(data, list):
            for item in data:
                data_el.appendChild(self._render_data(xml, 'item', item))
        elif isinstance(data, dict):
            self._render_dict(xml, data_el, data)
        elif hasattr(data, '__dict__'):
            self._render_dict(xml, data_el, data.__dict__)
        elif data != None:
            data_el.appendChild(xml.createTextNode(str(data)))
        
        return data_el

