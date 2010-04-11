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

    images = []

    for b in conn.get_all_buckets():
        k = boto.s3.key.Key(b)
        k.key = 'info.json'
        images.append(anyjson.deserialize(k.get_contents_as_string()))

    return render_response(action, request_id, images)
    

def render_response(action, request_id, response_data):
    xml = minidom.Document()
    
    response_el = xml.createElement(action + 'Response')
    response_el.setAttribute('xmlns', 'http://ec2.amazonaws.com/doc/2009-11-30/')
    
    request_id_el = xml.createElement('requestId')
    request_id_el.appendChild(xml.createTextNode(request_id))
    
    list_el = xml.createElement('imagesSet')
    
    for item in response_data:
        list_el.appendChild(render_item(xml, 'item', item))
    
    response_el.appendChild(list_el)
    xml.appendChild(response_el)
    
    _log.debug(xml.toxml())
    return xml.toxml()

def render_item(xml, el_name, item):
    item_el = xml.createElement(el_name)
    
    for key in item.keys():
        data = item[key]
        data_el = xml.createElement(key)
        
        if data is dict:
            data_el.appendChild(render_item(xml, key, data))
        elif data != None:
            data_el.appendChild(xml.createTextNode(str(data)))
        
        item_el.appendChild(data_el)
    
    return item_el

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