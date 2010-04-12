# vim: tabstop=4 shiftwidth=4 softtabstop=4
import logging
import random

import contrib
from twisted.internet import defer
import anyjson
import boto
import boto.s3

import settings
import calllib

CLOUD_TOPIC='cloud'

class CloudController(object):
    def __init__(self, options):
        self.volumes = {"result": "uninited"}
        self.instances = {"result": "uninited"}
        self.images = {"result":"uninited"}
        self.options = options

    def __str__(self):
        return 'CloudController'

    def get_console_output(self, request_id, **kwargs):
        # TODO : Make this use deferred instead
        instance_id = kwargs['InstanceId.1'][0]
        return calllib.call_sync('node', {"method": "get_console_output", "args" : {"instance_id": instance_id}})

    def describe_volumes(self, request_id, **kwargs):
        return self.volumes

    def list_volumes(self, request_id, **kwargs):
        return self.describe_volumes(request_id, kwargs)

    def create_volume(self, request_id, **kwargs):
        size = kwargs['Size'][0]
        calllib.cast('storage', {"method": "create_volume", "args" : {"size": size}})
        return {'result': 'ok'}

    def attach_volume(self, request_id, **kwargs):
        volume_id = kwargs['VolumeId'][0]
        instance_id = kwargs['InstanceId'][0]
        mountpoint = kwargs['Device'][0]
        calllib.cast('storage', {"method": "attach_volume", "args" : 
           {"volume_id": volume_id, "instance_id" : instance_id, "mountpoint" : mountpoint}})
        return {'result': 'ok'}

    def detach_volume(self, request_id, **kwargs):
        volume_id = kwargs['VolumeId'][0]
        calllib.cast('storage', {"method": "detach_volume", "args" : 
           {"volume_id": volume_id}})
        return {'result': 'ok'}

    def describe_instances(self, request_id, **kwargs):
        return self.instances

    def run_instances(self, request_id, **kwargs):
        reservation_id = 'r-%06d' % random.randint(0,1000000)
        for num in range(int(kwargs['MaxCount'][0])):
            instance_id = 'i-%06d' % random.randint(0,1000000)
            calllib.call('node', {"method": "run_instance", "args" : {"instance_id": instance_id}})

        return {'result': 'ok'}

    def terminate_instances(self, request_id, **kwargs):
        # TODO: Support multiple instances
        instance_id = kwargs['InstanceId'][0]
        calllib.cast('node', {"method": "terminate_instance", "args" : {"instance_id": instance_id}})
        return {'result': 'ok'}
        

    def delete_volume(self, request_id, **kwargs):
        volume_id = kwargs['VolumeId'][0]
        calllib.cast('storage', {"method": "delete_volume", "args" : {"volume_id": volume_id}})
        return {'result': 'ok'}

    def describe_images(self, request_id, **kwargs):
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
        
        return images

    def update_state(self, topic, value):
        logging.debug("Updating state for %s" % (topic))
        setattr(self, topic, value)



