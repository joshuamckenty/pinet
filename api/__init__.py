import logging

from xml.dom import minidom

_log = logging.getLogger()

def invoke_method(action, **kwargs):
    # TODO: Add api validation.
    # validate(action, **kwargs)
    
    # TODO: Enqueue request.
    # response_data = call(action, **kwargs)
    response_data = \
    [
        {
            'imageId': 'emi-CD1310B7',
            'imageOwnerId': 'admin',
            'isPublic': 'true',
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
            'imageId': 'emi-BB7610C2',
            'imageOwnerId': 'admin',
            'isPublic': 'true',
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
    
    return render_response(action, response_data)
    

def render_response(action, response_data):
    xml = minidom.Document()
    
    response_el = xml.createElement(action + 'Response')
    response_el.setAttribute('xmlns', 'http://ec2.amazonaws.com/doc/2009-11-30/')
    
    request_id_el = xml.createElement('requestId')
    request_id_el.appendChild(xml.createTextNode('558c80e8-bd18-49ff-8479-7bc176e12415'))
    
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
            data_el.appendChild(xml.createTextNode(data))
        
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