import logging
from xml.dom import minidom

_log = logging.getLogger()

RESPONSE_XMLNS = 'http://ec2.amazonaws.com/doc/2009-11-30/'

def invoke_method(action, **kwargs):
    # TODO: Validate API call
    # validate(action, **kwargs)
    
    # TODO: Add action and params to queue
    #       Loop until response (with timeout)
    response_data = \
    [
        {
            'imageId':              'emi-CD1310B7',
            'imageLocation':        'test/test1.manifest.xml',
            'imageState':           'available',
            'imageOwnerId':         'admin',
            'isPublic':             'true',
            'productCodes':         None,
            'architecture':         'x86_64',
            'imageType':            'machine',
            'kernelId':             'eki-218811E8',
            'ramdiskId':            'eri-5CB612F8',
            'rootDeviceType':       'instance-store',
            'rootDeviceName':       '/dev/sda1',
            'blockDeviceMapping':   None
        },
        {
            'imageId':              'emi-BC1210B9',
            'imageLocation':        'test/test2.manifest.xml',
            'imageState':           'available',
            'imageOwnerId':         'admin',
            'isPublic':             'true',
            'productCodes':         None,
            'architecture':         'x86_64',
            'imageType':            'machine',
            'kernelId':             'eki-218811E8',
            'ramdiskId':            'eri-5CB612F8',
            'rootDeviceType':       'instance-store',
            'rootDeviceName':       '/dev/sda1',
            'blockDeviceMapping':   None
        },
    ]
    
    return render_response(action, response_data)
    
def render_response(action, response_data):
    xml = minidom.Document()
    
    response_el = xml.createElement('%sResponse' % action)
    response_el.setAttribute('xmlns', RESPONSE_XMLNS)
    
    # TODO: Replace this with real request ID.
    request_id_el = xml.createElement('requestId')
    request_id_text = xml.createTextNode('558c80e8-bd18-49ff-8479-7bc176e12415')
    request_id_el.appendChild(request_id_text)
    response_el.appendChild(request_id_el)
    
    # TODO: Programmatically determine response container name.
    list_el = xml.createElement('imagesSet')
    
    for item in response_data:
        item_el = render_item(xml, 'item', item)
        list_el.appendChild(item_el)
        
    response_el.appendChild(list_el)
    
    xml.appendChild(response_el)
    
    _log.debug(xml.toxml())
    return xml.toxml()
    
def render_item(xml, name, item):
    item_el = xml.createElement(name)
    
    if type(item) is dict:
        for key in item.keys():
            data = item[key]
            if data:
                data_el = render_item(xml, key, data)
                item_el.appendChild(data_el)  
    else:
        item_text = xml.createTextNode(item)
        item_el.appendChild(item_text)
        
    return item_el
            
"""
<DescribeImagesResponse xmlns="http://ec2.amazonaws.com/doc/2009-11-30/">
    <requestId>558c80e8-bd18-49ff-8479-7bc176e12415</requestId>
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

<DescribeImagesResponse xmlns="http://ec2.amazonaws.com/doc/2009-11-30/">
    <requestId>558c80e8-bd18-49ff-8479-7bc176e12415</requestId>
    <imagesSet>
        <item>
            <imageId>emi-CD1310B7</imageId>
            <imageLocation>nebula/nebula-cloudpipe.manifest.xml</imageLocation>
            <imageState>available</imageState>
            <imageOwnerId>admin</imageOwnerId>
            <isPublic>true</isPublic>
            <productCodes/>
            <architecture>x86_64</architecture>
            <imageType>machine</imageType>
            <kernelId>eki-218811E8</kernelId>
            <ramdiskId>eri-5CB612F8</ramdiskId>
            <rootDeviceType>instance-store</rootDeviceType>
            <rootDeviceName>/dev/sda1</rootDeviceName>
            <blockDeviceMapping/>
        </item>
        <item>
            <imageId>emi-2DB60D30</imageId>
            <imageLocation>dashboard/dash.manifest.xml</imageLocation>
            <imageState>available</imageState>
            <imageOwnerId>admin</imageOwnerId>
            <isPublic>true</isPublic>
            <productCodes/>
            <architecture>x86_64</architecture>
            <imageType>machine</imageType>
            <kernelId>eki-218811E8</kernelId>
            <ramdiskId>eri-5CB612F8</ramdiskId>
            <rootDeviceType>instance-store</rootDeviceType>
            <rootDeviceName>/dev/sda1</rootDeviceName>
            <blockDeviceMapping/>
        </item>
        <item>
            <imageId>eri-5CB612F8</imageId>
            <imageLocation>ubuntu/initrd.img-karmic-x86_64.manifest.xml</imageLocation>
            <imageState>available</imageState>
            <imageOwnerId>admin</imageOwnerId>
            <isPublic>true</isPublic>
            <productCodes/><architecture>x86_64</architecture>
            <imageType>ramdisk</imageType>
            <rootDeviceType>instance-store</rootDeviceType>
            <rootDeviceName>/dev/sda1</rootDeviceName>
            <blockDeviceMapping/>
        </item>
        <item>
            <imageId>eki-218811E8</imageId>
            <imageLocation>ubuntu/vmlinuz-karmic-x86-64.manifest.xml</imageLocation>
            <imageState>available</imageState>
            <imageOwnerId>admin</imageOwnerId>
            <isPublic>true</isPublic><productCodes/>
            <architecture>x86_64</architecture>
            <imageType>kernel</imageType>
            <rootDeviceType>instance-store</rootDeviceType>
            <rootDeviceName>/dev/sda1</rootDeviceName>
            <blockDeviceMapping/>
        </item>
    </imagesSet>
</DescribeImagesResponse>
"""