# vim: tabstop=4 shiftwidth=4 softtabstop=4
import os
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
import urllib
import time
import node
import network
import utils
from utils import runthis
import exception

FLAGS = flags.FLAGS
flags.DEFINE_string('cloud_topic', 'cloud', 'the topic clouds listen on')
flags.DEFINE_string('keys_path', './keys', 'Where we keep our keys')
flags.DEFINE_string('ca_path', './CA', 'Where we keep our root CA')
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
        self.volumes = {}
        self.instances = {}
        self.images = {"result":"uninited"}
        self.network = network.NetworkController()

    def __str__(self):
        return 'CloudController'
    
    def setup(self):
        # Create keys folder, if it doesn't exist
        if not os.path.exists(FLAGS.keys_path):
            os.makedirs(os.path.abspath(FLAGS.keys_path))
        # Gen root CA, if we don't have one
        root_ca_path = os.path.join(FLAGS.ca_path, 'cacert.pem')
        if not os.path.exists(root_ca_path):
            start = os.getcwd()
            os.chdir(FLAGS.ca_path)
            runthis("Generating root CA: %s", "sh genrootca.sh")
            os.chdir(start)
            # TODO: Do this with M2Crypto instead

    def fetch_ca(self):
        return open(os.path.join(FLAGS.ca_path, 'cacert.pem')).read()
                          
    def describe_key_pairs(self, context, key_names=None, **kwargs):
        key_pairs = { 'keypairsSet': [] }
        key_names = key_names and key_names or []
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

    def _get_user_id(self, context):
        if context and context.user:
            return context.user.id
        else:
            return None

    def describe_volumes(self, context, **kwargs):
        user_id = self._get_user_id(context)
        if self.volumes == {}:
            return {'volumeSet': [] } 
        volumes = []
        for storage in self.volumes.values():
            for volume in storage.values():
                if user_id == None or user_id == volume['user_id']:
                    v = volumes.copy()
                    del v['user_id']
                    volumes.append(v)
        return defer.succeed({'volumeSet': volumes})

    def create_volume(self, context, size, **kwargs):
        user_id = self._get_user_id(context)
        calllib.cast('storage', {"method": "create_volume", 
                                 "args" : {"size": size,
                                           "user_id": user_id}})
        return defer.succeed(True)

    def _get_by_id(self, workers, id):
        if workers == {}:
            raise exception.ApiError("%s not found in %s", id, workers)
        for worker in workers.values():
            if worker.has_key(id):
                return worker[id]
        raise exception.ApiError("%s not found in %s", id, workers)

    def _get_volume(self, volume_id):
        return self._get_by_id(self.volumes, volume_id)


    def _get_instance(self, instance_id):
        return self._get_by_id(self.instances, instance_id)


    def attach_volume(self, context, volume_id, instance_id, device, **kwargs):
        user_id = self._get_user_id(context)
        volume = self._get_volume(volume_id)
        if volume['user_id'] != user_id:
            raise exception.ApiError("%s doesn't own %s", user_id, volume_id)
        instance = self._get_instance(instance_id)
        if instance['user_id'] != user_id:
            raise exception.ApiError("%s doesn't own %s", user_id, instance_id)
            
        aoe_device = volume['aoe_device']
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
        user_id = self._get_user_id(context)
        # TODO(joshua): Make sure the updated state has been received first
        volume = self._get_volume(volume_id)
        if volume['user_id'] != user_id:
            raise exception.ApiError("%s doesn't own %s", user_id, volume_id)
        instance_id = volume['instance_id']
        instance = self._get_instance(instance_id)
        if instance['user_id'] != user_id:
            raise exception.ApiError("%s doesn't own %s", user_id, instance_id)
        mountpoint = volume['mountpoint']
        calllib.cast('node', {"method": "detach_volume",
                                 "args" : {"instance_id": instance_id,
                                           "mountpoint": mountpoint}})
        calllib.cast('storage', {"method": "detach_volume",
                                 "args" : {"volume_id": volume_id}})
        return defer.succeed(True)

    def _convert_to_set(self, lst, str):
        if lst == None or lst == []:
            return None
        return [{str: x} for x in lst]

    def describe_instances(self, context, **kwargs):
        user_id = self._get_user_id(context)
        return defer.succeed(self.format_instances(user_id))

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
        logging.debug("Going to run instances...")
        # logging.debug(kwargs)
        
        kwargs['owner_id'] = self._get_user_id(context)
        if kwargs.has_key('key_name') and context and context.user:
            key_pair = context.user.get_key_pair(kwargs['key_name'])
            if not key_pair:
                raise exception.ApiError('Key Pair %s not found' %
                                         kwargs['key_name'])
            kwargs['key_data'] = key_pair.public_key 
        kwargs['reservation_id'] = 'r-%06d' % random.randint(0,1000000)
        kwargs['launch_time'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        pending = {}
        for num in range(int(kwargs['max_count'])):
            kwargs['instance_id'] = 'i-%06d' % random.randint(0,1000000)
            kwargs['mac_address'] = utils.generate_mac()
            #TODO(joshua) - Allocate IP based on security group
            kwargs['ami_launch_index'] = num 
            (address, kwargs['network_name']) = self.network.allocate_address(kwargs['owner_id'], mac=kwargs['mac_address'])
            kwargs['private_dns_name'] = str(address)
            logging.debug("Casting to node for an instance with IP of %s in the %s network" % (kwargs['private_dns_name'], kwargs['network_name']))
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
        self.boto_conn().make_request(
                method='DELETE', 
                bucket='_images', 
                query_args=qs({'image_id': image_id}))
                
        return defer.succeed({'imageId': image_id})
            
    def register_image(self, context, image_location, **kwargs):
        image_id = 'ami-%06d' % random.randint(0,1000000)
        
        rval = self.boto_conn().make_request(
                method='PUT', 
                bucket='_images', 
                query_args=qs({'image_location': image_location,
                               'image_id': image_id,
                               'user_id': kwargs['user'].id}))
        
        logging.debug("Registering %s" % image_location)
        return defer.succeed({'imageId': image_id})

    def update_state(self, topic, value):
        """ accepts status reports from the queue and consolidates them """
        logging.debug("Updating state for %s" % (topic))
        # TODO(termie): do something smart here to aggregate this data
        # TODO(jmc): This is fugly
        # TODO(jmc): if an instance has disappeared from the node, call instance_death
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
            
    def _parse_list_param(self, name, params):
        """
        Describe methods take an array of names for parameters.
        For example, DescribeKeyPairs can have:
        KeyName.1, KeyName.2, ... KeyName.N        
        This helper will return a list of values for 'KeyName'.
        """
        values = []
        i = 1
        key = '%s.%d' % (name, i)
        while key in params:
            values.append(params[key][0])
            i += 1
            key = '%s.%d' % (name, i)
        return values

def qs(params):
    pairs = []
    for key in params.keys():
        pairs.append(key + '=' + urllib.quote(params[key]))
    return '&'.join(pairs)
