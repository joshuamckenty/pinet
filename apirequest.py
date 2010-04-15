import logging
import random
import re
from xml.dom import minidom

from twisted.internet import defer


_log = logging.getLogger()


camelcase_to_underscore = lambda str: re.sub('(((?<=[a-z])[A-Z])|([A-Z](?![A-Z]|$)))', '_\\1', str).lower().strip('_')


class APIRequest(object):
    def __init__(self, controller, action):
        self.controller = controller
        self.action = action
        self.request_id = None

    def send(self, **kwargs):
        self.request_id = ''.join([random.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890-') for x in xrange(20)])
    
        try:
            method = getattr(self.controller, camelcase_to_underscore(self.action))
        except AttributeError:
            _error = 'Unsupported API request: controller = %s, action = %s' % (self.controller, self.action)
            _log.warning(_error)
            # TODO: Raise custom exception, trap in apiserver, reraise as 400 error.
            raise Exception(_error)

        d = defer.maybeDeferred(method, self.request_id, **kwargs)
        d.addCallback(self._render_response)

        return d

    def _render_response(self, response_data):
        xml = minidom.Document()
    
        response_el = xml.createElement(self.action + 'Response')
        response_el.setAttribute('xmlns', 'http://ec2.amazonaws.com/doc/2009-11-30/')
    
        request_id_el = xml.createElement('requestId')
        request_id_el.appendChild(xml.createTextNode(self.request_id))
        response_el.appendChild(request_id_el)
        
        self._render_dict(xml, response_el, response_data)
    
        xml.appendChild(response_el)
    
        response = xml.toxml()
        xml.unlink()

        _log.debug(response)

        return response
    
    def _render_dict(self, xml, el, data):
        # import pdb; pdb.set_trace()
        _log.debug(dir(data))
        try:
            for key in data.keys():
                val = data[key]
                if val:
                    el.appendChild(self._render_data(xml, key, val))
        except:
            _log.debug(data)
            raise

    def _render_data(self, xml, el_name, data):
        data_el = xml.createElement(el_name)
    
        if isinstance(data, list):
            for item in data:
                data_el.appendChild(self._render_data(xml, 'item', item))
        elif isinstance(data, dict):
            self._render_dict(xml, data_el, data)
        elif data != None:
            data_el.appendChild(xml.createTextNode(str(data)))
        
        return data_el

