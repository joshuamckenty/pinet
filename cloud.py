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
        self.volumes = None
        self.instances = None
        self.images = None
        self.options = options

    def __str__(self):
        return 'CloudController'

    def get_console_output(self, request_id, **kwargs):
        # TODO : Make this use deferred instead
        instance_id = kwargs['InstanceId.1'][0]
        return calllib.call_sync('node', {"method": "get_console_output", "args" : {"instance_id": instance_id}})

    def describe_volumes(self, request_id, **kwargs):
        return self.volumes

    def describe_instances(self, request_id, **kwargs):
        return self.instances

    def run_instances(self, request_id, **kwargs):
        reservation_id = 'r-%06d' % random.randint(0,1000000)
        for num in range(int(kwargs['MaxCount'][0])):
            instance_id = 'i-%06d' % random.randint(0,1000000)
            calllib.call('node', {"method": "run_instance", "args" : {"instance_id": instance_id}})

        return {'result': 'ok'}

    def terminate_instances(self, request_id, **kwargs):
        pass

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



