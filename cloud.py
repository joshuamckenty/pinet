# vim: tabstop=4 shiftwidth=4 softtabstop=4
import logging
import random

import contrib
import anyjson
import boto
import boto.s3
from twisted.internet import defer

import calllib
import flags
import users
import time
import node

FLAGS = flags.FLAGS
flags.DEFINE_string('cloud_topic', 'cloud', 'the topic clouds listen on')
flags.DEFINE_integer('s3_port', 3333, 'the port we connect to s3 on')


_STATE_NAMES = {
    node.Instance.NOSTATE: 'nostate',
    node.Instance.RUNNING: 'running',
    node.Instance.BLOCKED: 'blocked',
    node.Instance.PAUSED: 'paused',
    node.Instance.SHUTDOWN: 'shutdown',
    node.Instance.SHUTOFF: 'shutoff',
    node.Instance.CRASHED: 'crashed',
}

class CloudController(object):
    def __init__(self):
        self.volumes = {"result": "uninited"}
        self.instances = None
        self.images = {"result":"uninited"}

    def __str__(self):
        return 'CloudController'

    def create_key_pair(self, request_id, **kwargs):
        key_name = kwargs['KeyName'][0]
        user = kwargs['user']
        try:
            private_key, fingerprint = user.generate_key_pair(key_name)
            return {'keyName': key_name,
                    'keyFingerprint': fingerprint,
                    'keyMaterial': private_key }
        except users.UserError, e:
            raise

    def delete_key_pair(self, request_id, **kwargs):
        key_name = kwargs['KeyName'][0]
        user = kwargs['user']
        # aws returns true even if the key doens't exist
        user.delete_key_pair(key_name)
        return True

    def get_console_output(self, request_id, **kwargs):
        # TODO(termie): move this InstanceId stuff into the api layer
        instance_id = kwargs['InstanceId.1'][0]
        return calllib.call('node', {"method": "get_console_output",
                                     "args" : {"instance_id": instance_id}})

    def describe_volumes(self, request_id, **kwargs):
        return defer.succeed(self.volumes)

    def create_volume(self, request_id, **kwargs):
        # TODO(termie): API layer
        size = kwargs['Size'][0]
        calllib.cast('storage', {"method": "create_volume", 
                                 "args" : {"size": size}})
        return defer.succeed(True)
    
    def _get_volume(self, volume_id):
        for item in self.volumes['volumeSet']:
            if item['item']['volumeId'] == volume_id:
                return item['item']
        return None


    def attach_volume(self, request_id, **kwargs):
        # TODO(termie): API layer
        volume_id = kwargs['VolumeId'][0]
        instance_id = kwargs['InstanceId'][0]
        mountpoint = kwargs['Device'][0]
        aoe_device = self._get_volume(volume_id)['aoe_device']
        # Needs to get right node controller for attaching to
        # TODO: Maybe have another exchange that goes to everyone?
        calllib.cast('node', {"method": "attach_volume",
                                 "args" : {"aoe_device": aoe_device,
                                           "instance_id" : instance_id,
                                           "mountpoint" : mountpoint}})
        calllib.cast('storage', {"method": "attach_volume",
                                 "args" : {"volume_id": volume_id,
                                           "instance_id" : instance_id,
                                           "mountpoint" : mountpoint}})
        return defer.succeed(True)

    def detach_volume(self, request_id, **kwargs):
        # TODO(termie): API layer
        # TODO(jmc): Make sure the updated state has been received first
        volume_id = kwargs['VolumeId'][0]
        volume = self._get_volume(volume_id)
        mountpoint = volume['mountpoint']
        instance_id = volume['instance_id']
        calllib.cast('node', {"method": "detach_volume",
                                 "args" : {"instance_id": instance_id,
                                           "mountpoint": mountpoint}})
        calllib.cast('storage', {"method": "detach_volume",
                                 "args" : {"volume_id": volume_id}})
        return defer.succeed({'result': 'ok'})

    def describe_instances(self, request_id, user, **kwargs):
        return defer.succeed(self.format_instances(user.id))
    
    def _convert_to_set(self, lst, str):
        if lst == None or lst == []:
            return None
        return [{str: x} for x in lst]


    def format_instances(self, owner_id = None):
        reservations = {}
        for node in self.instances.values():
            for instance in node:
                if owner_id == None or owner_id == instance['owner_id']:
                    i = {}
                    i['instance_id'] = instance['instance_id']
                    i['image_id'] = instance['image_id']
                    i['instance_state'] = {
                        'code': instance['state'],
                        'name': _STATE_NAMES[instance['state']]
                    }
                    i['private_dns_name'] = instance['private_dns_name']
                    i['dns_name'] = instance['dns_name']
                    i['key_name'] = instance['key_name']
                    i['product_codes_set'] = self._convert_to_set(
                        instance['product_codes'], 'product_code')
                    i['instance_type'] = instance['instance_type']
                    i['launch_time'] = instance['launch_time']
                    if not reservations.has_key(instance['reservation_id']):
                        r = {}
                        r['reservation_id'] = instance['reservation_id']
                        r['owner_id'] = instance['owner_id']
                        r['group_set'] = self._convert_to_set(
                            instance['groups'], 'group_id')
                        r['instance_set'] = []
                        reservations[instance['reservation_id']] = r
                    reservations[instance['reservation_id']]['instance_set'].append(i)

        instance_response = {'reservationSet' : list(reservations.values()) }
        return instance_response

    def run_instances(self, request_id, user, kwargsnew, **kwargs):
        # TODO(termie): API layer
        logging.debug(kwargsnew)
        kwargsnew['owner_id'] = user.id

        kwargsnew['reservation_id'] = 'r-%06d' % random.randint(0,1000000)
        kwargsnew['launch_time'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        l = []
        for num in range(int(kwargsnew['max_count'])):
            kwargsnew['instance_id'] = 'i-%06d' % random.randint(0,1000000)
            kwargsnew['launch_index'] = num 
            l.append(calllib.cast('node', 
                                  {"method": "run_instance", 
                                   "args" : kwargsnew 
                                            }))
        d = defer.gatherResults(l)
        logging.debug(d)
        #TODO(Vish):return proper info
        return d
    
    def terminate_instances(self, request_id, **kwargs):
        # TODO: Support multiple instances
        # TODO(termie): API layer
        instance_id = kwargs['InstanceId.1'][0]
        calllib.cast('node', {"method": "terminate_instance",
                              "args" : {"instance_id": instance_id}})
        return defer.succeed(True)
        
    def delete_volume(self, request_id, **kwargs):
        # TODO(termie): API layer
        volume_id = kwargs['VolumeId'][0]
        calllib.cast('storage', {"method": "delete_volume",
                                 "args" : {"volume_id": volume_id}})
        return defer.succeed(True)

    def describe_images(self, request_id, **kwargs):
        conn = boto.s3.connection.S3Connection (
            aws_secret_access_key="fixme",
            aws_access_key_id="fixme",
            is_secure=False,
            calling_format=boto.s3.connection.OrdinaryCallingFormat(),
            debug=0,
            port=FLAGS.s3_port,
            host='localhost',
        )

        images = { 'imagesSet': [] }

        for b in conn.get_all_buckets():
            k = boto.s3.key.Key(b)
            k.key = 'info.json'
            images['imagesSet'].append(
                    anyjson.deserialize(k.get_contents_as_string()))
        
        return defer.succeed(images)

    def update_state(self, topic, value):
        """ accepts status reports from the queue and consolidates them """
        logging.debug("Updating state for %s" % (topic))
        # TODO(termie): do something smart here to aggregate this data
        # TODO(jmc): This is fugly
        if "node" == topic:
            getattr(self, topic)[value.keys()[0]] = value.values()[0]
        else:
            setattr(self, topic, value)
        return defer.succeed(True)



