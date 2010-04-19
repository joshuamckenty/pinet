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
    node.Instance.NOSTATE: 'pending',
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
        self.instances = {}
        self.images = {"result":"uninited"}

    def __str__(self):
        return 'CloudController'
                          
    def describe_key_pairs(self, context, key_names, **kwargs):
        key_pairs = { 'keypairsSet': [] }

        if len(key_names) > 0:
            for key_name in key_names:
                key_pair = context.user.get_key_pair(key_name)
                if key_pair != None:
                    key_pairs['keypairsSet'].append({
                        'keyName': key_pair.name,
                        'keyFingerprint': key_pair.fingerprint,
                    })
        else:
            for key_pair in context.user.get_key_pairs():
                key_pairs['keypairsSet'].append({
                    'keyName': key_pair.name,
                    'keyFingerprint': key_pair.fingerprint,
                })

        return key_pairs

    def create_key_pair(self, context, key_name, **kwargs):
        try:
            private_key, fingerprint = context.user.generate_key_pair(key_name)
            return {'keyName': key_name,
                    'keyFingerprint': fingerprint,
                    'keyMaterial': private_key }
        except users.UserError, e:
            raise

    def delete_key_pair(self, context, key_name, **kwargs):
        context.user.delete_key_pair(key_name)
        # aws returns true even if the key doens't exist
        return True
        
    def describe_security_groups(self, context, group_names, **kwargs):
        groups = { 'securityGroupSet': [] }

        # Stubbed for now to unblock other things.
        return groups
        
    def create_security_group(self, context, group_name, **kwargs):
        pass
        
    def delete_security_group(self, context, group_name, **kwargs):
        pass

    def get_console_output(self, context, instance_id, **kwargs):
        # instance_id is passed in as a list of instances
        instance_id = instance_id[0]
        return calllib.call('node', {"method": "get_console_output",
                                     "args" : {"instance_id": instance_id}})

    def describe_volumes(self, context, **kwargs):
        # TODO: Evil - this returns every volume for every user.
        return defer.succeed(self.volumes)

    def create_volume(self, context, size, **kwargs):
        # TODO(termie): API layer
        # TODO: We need to pass in context.user so we can associate the volume with the user.
        calllib.cast('storage', {"method": "create_volume", 
                                 "args" : {"size": size}})
        return defer.succeed(True)
    
    def _get_volume(self, volume_id):
        for item in self.volumes['volumeSet']:
            if item['item']['volumeId'] == volume_id:
                return item['item']
        return None


    def attach_volume(self, context, volume_id, instance_id, device, **kwargs):
        # TODO(termie): API layer
        # TODO: We need to verify that context.user owns both the volume and the instance before attaching.
        aoe_device = self._get_volume(volume_id)['aoe_device']
        # Needs to get right node controller for attaching to
        # TODO: Maybe have another exchange that goes to everyone?
        calllib.cast('node', {"method": "attach_volume",
                                 "args" : {"aoe_device": aoe_device,
                                           "instance_id" : instance_id,
                                           "mountpoint" : device}})
        calllib.cast('storage', {"method": "attach_volume",
                                 "args" : {"volume_id": volume_id,
                                           "instance_id" : instance_id,
                                           "mountpoint" : device}})
        return defer.succeed(True)

    def detach_volume(self, context, volume_id, **kwargs):
        # TODO(termie): API layer
        # TODO(jmc): Make sure the updated state has been received first
        # TODO: We need to verify that context.user owns both the volume and the instance before dettaching.
        volume = self._get_volume(volume_id)
        mountpoint = volume['mountpoint']
        instance_id = volume['instance_id']
        calllib.cast('node', {"method": "detach_volume",
                                 "args" : {"instance_id": instance_id,
                                           "mountpoint": mountpoint}})
        calllib.cast('storage', {"method": "detach_volume",
                                 "args" : {"volume_id": volume_id}})
        return defer.succeed({'result': 'ok'})

    def _convert_to_set(self, lst, str):
        if lst == None or lst == []:
            return None
        return [{str: x} for x in lst]

    def describe_instances(self, context, **kwargs):
        return defer.succeed(self.format_instances(context.user.id))

    def format_instances(self, owner_id = None, reservation_id = None):
        if self.instances == {}:
            return {'reservationSet': []}
        reservations = {}
        for node in self.instances.values():
            for instance in node.values():
                res_id = instance.get('reservation_id', 'Unknown')
                if ((owner_id == None
                    or owner_id == instance.get('owner_id', None))
                    and (reservation_id == None
                    or reservation_id == res_id)):
                    i = {}
                    i['instance_id'] = instance.get('instance_id', None)
                    i['image_id'] = instance.get('image_id', None)
                    i['instance_state'] = {
                        'code': instance.get('state', None),
                        'name': _STATE_NAMES[instance.get('state', None)]
                    }
                    i['private_dns_name'] = instance.get('private_dns_name', None)
                    i['dns_name'] = instance.get('dns_name', None)
                    i['key_name'] = instance.get('key_name', None)
                    i['product_codes_set'] = self._convert_to_set(
                        instance.get('product_codes', None), 'product_code')
                    i['instance_type'] = instance.get('instance_type', None)
                    i['launch_time'] = instance.get('launch_time', None)
                    i['ami_launch_index'] = instance.get('ami_launch_index',
                                                         None)
                    if not reservations.has_key(res_id):
                        r = {}
                        r['reservation_id'] = res_id
                        r['owner_id'] = instance.get('owner_id', None)
                        r['group_set'] = self._convert_to_set(
                            instance.get('groups', None), 'group_id')
                        r['instances_set'] = []
                        reservations[res_id] = r
                    reservations[res_id]['instances_set'].append(i)

        instance_response = {'reservationSet' : list(reservations.values()) }
        return instance_response

    def run_instances(self, context, **kwargs):
        # passing all of the kwargs on to node.py
        logging.debug(kwargs)
        if context and context.user:
            kwargs['owner_id'] = context.user.id
        else:
            kwargs['owner_id'] = None

        kwargs['reservation_id'] = 'r-%06d' % random.randint(0,1000000)
        kwargs['launch_time'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        pending = {}
        for num in range(int(kwargs['max_count'])):
            kwargs['instance_id'] = 'i-%06d' % random.randint(0,1000000)
            kwargs['ami_launch_index'] = num 
            calllib.cast('node', 
                                  {"method": "run_instance", 
                                   "args" : kwargs 
                                            })
            pending[kwargs['instance_id']] = kwargs
            pending[kwargs['instance_id']]['state'] = node.Instance.NOSTATE

        
        # TODO(vish): pending instances will be lost on crash
        if(not self.instances.has_key('pending')):
            self.instances['pending'] = {}

        self.instances['pending'].update(pending)
        return defer.succeed(self.format_instances(kwargs['owner_id'],
                                                   kwargs['reservation_id']))
    
    def terminate_instances(self, context, instance_id, **kwargs):
        for i in instance_id:
            calllib.cast('node', {"method": "terminate_instance",
                              "args" : {"instance_id": i}})
        return defer.succeed(True)
        
    def delete_volume(self, context, volume_id, **kwargs):
        calllib.cast('storage', {"method": "delete_volume",
                                 "args" : {"volume_id": volume_id}})
        return defer.succeed(True)

    def describe_images(self, context, **kwargs):
        # TODO: Make this aware of the difference between private and public images.
        images = { 'imagesSet': [] }

        for bucket in self.boto_conn().get_all_buckets():
            try:
                k = boto.s3.key.Key(bucket)
                k.key = 'info.json'
                images['imagesSet'].append(
                        anyjson.deserialize(k.get_contents_as_string()))
            except Exception:
                pass
        
        return defer.succeed(images)
    
    def deregister_image(self, context, image_id, **kwargs):
        # TODO: Make sure context.user has permission to deregister.
        bucket = self.boto_conn().get_bucket(image_id)
        k = boto.s3.key.Key(bucket)
        k.key = 'info.json'
        bucket.delete_key(k)
        k.key = 'image'
        bucket.delete_key(k)

        return defer.succeed({'imageId': image_id})
            
    def register_image(self, context, image_location, **kwargs):
        image_id = 'ami-%06d' % random.randint(0,1000000)
        
        info = {
            'imageId': image_id,
            'imageLocation': image_location,
            'imageOwnerId': kwargs['user'].id,
            'imageState': 'available',
            'isPublic': 'true', # grab from bundle manifest
            'architecture': 'x86_64', # grab from bundle manifest
        }
        
        # FIXME: grab kernelId and ramdiskId from bundle manifest
        
        # FIXME: unbundle the image using the cloud private key
        #        saving it to "%s/image" % emi_id
        
        bucket = self.boto_conn().create_bucket(image_id)
        k = boto.s3.key.Key(bucket)
        k.key = 'info.json'
        k.set_contents_from_string(anyjson.serialize(info))
        k.key = 'image'
        k.set_contents_from_string('FIXME: decrypt image')
        
        logging.debug("Registering %s" % image_location)
        return defer.succeed({'imageId': image_id})

    def update_state(self, topic, value):
        """ accepts status reports from the queue and consolidates them """
        logging.debug("Updating state for %s" % (topic))
        # TODO(termie): do something smart here to aggregate this data
        # TODO(jmc): This is fugly
        if "node" == topic:
            getattr(self, topic)[value.keys()[0]] = value.values()[0]
        else:
            # TODO(vish): refactor this
            if "instances" == topic:
                for instance_id in value.values()[0].keys():
                    if (self.instances.has_key('pending') and
                        self.instances['pending'].has_key(instance_id)):
                        del self.instances['pending'][instance_id]
            setattr(self, topic, value)
        return defer.succeed(True)

    def boto_conn(self):
        # TODO: User context.user for the access and secret keys.
        return boto.s3.connection.S3Connection (
            aws_secret_access_key="fixme",
            aws_access_key_id="fixme",
            is_secure=False,
            calling_format=boto.s3.connection.OrdinaryCallingFormat(),
            debug=0,
            port=FLAGS.s3_port,
            host='localhost')

# vish: obsoleted by apirequest processing            
#    def _parse_list_param(self, name, params):
#        """
#        Describe methods take an array of names for parameters.
#        For example, DescribeKeyPairs can have:
#        KeyName.1, KeyName.2, ... KeyName.N        
#        This helper will return a list of values for 'KeyName'.
#        """
#        values = []
#        i = 1
#        key = '%s.%d' % (name, i)
#        while key in params:
#            values.append(params[key][0])
#            i += 1
#            key = '%s.%d' % (name, i)
#        return values  
