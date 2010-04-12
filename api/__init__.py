import logging
import random
import re

from xml.dom import minidom

_log = logging.getLogger()

camelcase_to_underscore = lambda str: re.sub('(((?<=[a-z])[A-Z])|([A-Z](?![A-Z]|$)))', '_\\1', str).lower().strip('_')

def handle_request(controller, action, **kwargs):
    request_id = ''.join([random.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890-') for x in xrange(20)])
    
    try:
        method = getattr(controller, camelcase_to_underscore(action))
    except AttributeError:
        _error = 'Unsupported API request: controller = %s, action = %s' % (controller, action)
        _log.warning(_error)
        # TODO: Raise custom exception, trap in apiserver, reraise as 400 error.
        raise Exception(_error)

    response_body = method(request_id, **kwargs)
    xml = render_response(request_id, action, response_body)
    _log.debug('%s.%s returned %s' % (controller, method, xml))
    
    return xml

def render_response(request_id, action, response_data):
    xml = minidom.Document()
    
    response_el = xml.createElement(action + 'Response')
    response_el.setAttribute('xmlns', 'http://ec2.amazonaws.com/doc/2009-11-30/')
    
    request_id_el = xml.createElement('requestId')
    request_id_el.appendChild(xml.createTextNode(request_id))
    
    render_dict(xml, response_el, response_data)
    
    xml.appendChild(response_el)
    
    response = xml.toxml()
    xml.unlink()
    _log.debug(response)
    return response
    
def render_dict(xml, el, data):
    for key in data.keys():
        val = data[key]
        if val:
            el.appendChild(render_data(xml, key, val))

def render_data(xml, el_name, data):
    data_el = xml.createElement(el_name)
    
    if isinstance(data, list):
        for item in data:
            data_el.appendChild(render_data(xml, 'item', item))
    elif isinstance(data, dict):
        render_dict(xml, data_el, data)
    elif data != None:
        data_el.appendChild(xml.createTextNode(str(data)))
        
    return data_el

