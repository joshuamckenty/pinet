import logging
import boto
import boto.s3
import settings

# THIS IS EVIL
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.split(__file__)[0], '..', 'contrib')))
import anyjson

from xml.dom import minidom

_log = logging.getLogger()

def invoke_request(action, **kwargs):
    # TODO: Generate a unique request ID.
    request_id = '558c80e8-bd18-49ff-8479-7bc176e12415'
    
    # TODO: Add api validation.
    # validate(action, **kwargs)
    
    # TODO: Enqueue request and poll for response.
    # response_data = call(action, **kwargs)
    
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

    return render_response(action, request_id, images)
    
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