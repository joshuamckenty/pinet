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

camelcase_to_underscore = lambda str: re.sub('(((?<=[a-z])[A-Z])|([A-Z](?![A-Z]|$)))', '_\\1', str).lower().strip('_')

def invoke_request(section, action, **kwargs):
    # TODO: Generate a unique request ID.
    request_id = '558c80e8-bd18-49ff-8479-7bc176e12415'
    
    # TODO: Add api validation.
    # validate(action, **kwargs)
    
<<<<<<< HEAD
    # Build request json.
    request = anyjson.serialize({
        'action': camelcase_to_underscoreaction,
        'args': kwargs
    })
    _log.debug('Enqueuing: topic = %s, msg = %s' % (section, request))
    
    
    # TODO: call_sync wants message param in json format only to
    #       immediately deserialize it again in the body of call_sync?

    # Enqueue request and poll for response.
    response_data = call_sync(section, request)
    
    """
=======
    # TODO: Enqueue request and poll for response.
    response_data = globals()[action](request_id, **kwargs)
    return response_data
    # getattr(self, action)(kwargs)

def DescribeVolumes(request_id, **kwargs):
    action = "DescribeVolumes"
    volumes = calllib.call_sync("cloud",  '{"method": "list_volumes"}')

    # volumes = { 'volumeSet': volumes }
    xml = render_response(action, request_id, volumes)
    _log.debug("DescribeVolumes is returning %s" % (xml))
    return xml

def DescribeInstances(request_id, **kwargs):
    action = "DescribeInstances"
    instances = calllib.call_sync("cloud",  '{"method": "list_instances"}')

    xml = render_response(action, request_id, instances)
    _log.debug("DescribeInstances is returning %s" % (xml))
    return xml

    
def DescribeImages(request_id, **kwargs):
    action = "DescribeImages"
>>>>>>> 44a5c642230dd8b6fe047487c7ef4d68244a7517
    conn = boto.s3.connection.S3Connection (
        aws_secret_access_key="fixme",
        aws_access_key_id="fixme",
        is_secure=False,
        calling_format=boto.s3.connection.OrdinaryCallingFormat(),
        debug=0,
        port=settings.S3_PORT,
        host='localhost',
    )

    images = { 'imagesSet': [] }

    for b in conn.get_all_buckets():
        k = boto.s3.key.Key(b)
        k.key = 'info.json'
        images['imagesSet'].append(anyjson.deserialize(k.get_contents_as_string()))
    """    

    return render_response(action, request_id, response_data)
    
    """
    Expected format for DescribeImages:
    
    response_data = \
    {
        'imagesSet':
        [
            {
                'imageOwnerId': 'admin',
                'isPublic': 'true',
                'imageId': 'emi-CD1310B7',
                'imageState': 'available',
                'kernelId': 'eki-218811E8',
                'architecture': 'x86_64',
                'imageLocation': 'test/test1.manifest.xml',
                'rootDeviceType': 'instance-store',
                'ramdiskId': 'eri-5CB612F8',
                'rootDeviceName': '/dev/sda1',
                'imageType': 'machine'
            },
            {
                'imageOwnerId': 'admin',
                'isPublic': 'true',
                'imageId': 'emi-AB1560D9',
                'imageState': 'available',
                'kernelId': 'eki-218811E8',
                'architecture': 'x86_64',
                'imageLocation': 'test/test1.manifest.xml',
                'rootDeviceType': 'instance-store',
                'ramdiskId': 'eri-5CB612F8',
                'rootDeviceName': '/dev/sda1',
                'imageType': 'machine'
            }
        ]
    }
    """
    
    return render_response(action, request_id, response_data)
    

def render_response(action, request_id, response_data):
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

"""
<DescribeImagesResponse xmlns="http://ec2.amazonaws.com/doc/2009-11-30/"><requestId>558c80e8-bd18-49ff-8479-7bc176e12415</requestId>
<imagesSet>
    <item>
        <imageOwnerId>admin</imageOwnerId>
        <isPublic>true</isPublic>
        <imageId>emi-CD1310B7</imageId>
        <imageState>available</imageState>
        <kernelId>eki-218811E8</kernelId>
        <architecture>x86_64</architecture>
        <imageLocation>test/test1.manifest.xml</imageLocation>
        <rootDeviceType>instance-store</rootDeviceType>
        <ramdiskId>eri-5CB612F8</ramdiskId>
        <rootDeviceName>/dev/sda1</rootDeviceName>
        <imageType>machine</imageType>
    </item>
</imagesSet>
</DescribeImagesResponse>
"""
