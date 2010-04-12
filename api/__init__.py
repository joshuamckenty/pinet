import logging
import os
import sys
import re

import boto
import boto.s3
import settings

# THIS IS EVIL
import contrib
import cloud
import calllib

import anyjson

from xml.dom import minidom
from calllib import call_sync

_log = logging.getLogger()

#camelcase_to_underscore = lambda str: re.sub('(((?<=[a-z])[A-Z])|([A-Z](?![A-Z]|$)))', '_\\1', str).lower().strip('_')

ACTION_MAP = {
    'Cloud': {
        'DescribeImages': ('cloud_controller', 'describe_images'),
        'DescribeInstances': ('cloud_controller', 'describe_instances'),
        'DescribeVolumes': ('cloud_controller', 'describe_volumes'),
    },
}


def handle_request(section, action, cloud_controller, **kwargs):
    # TODO: Generate a unique request ID.
    request_id = '558c80e8-bd18-49ff-8479-7bc176e12415'
    
    # TODO: Add api validation.
    # validate(action, **kwargs)
    
    # Build request json.
    try:
        controller_name, method = translate_request(section, action)
        _log.debug('Translated API request: controller = %s, method = %s' % (controller_name, method))
        controller = locals()[controller_name]
    except:
        controller = globals()[controller_name]
        _error = 'Unsupported API request: section = %s, action = %s' % (section, action)
        _log.warning(_error)
        # TODO: Raise custom exception, trap in apiserver, reraise as 400 error.
        # raise Exception(_error)

    return invoke_request(request_id, controller, action, method, **kwargs)

def translate_request(section, action):
    return ACTION_MAP[section][action]
    
def invoke_request(request_id, controller, action, method, **kwargs):
    response_body = getattr(controller, method)(request_id, **kwargs)
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

