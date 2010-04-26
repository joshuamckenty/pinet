# vim: tabstop=4 shiftwidth=4 softtabstop=4
import os
import logging
import random
import copy

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
import crypto
import network
import utils
from utils import runthis
import exception
import crypto
import images
import base64
import tornado

FLAGS = flags.FLAGS
flags.DEFINE_string('cloud_topic', 'cloud', 'the topic clouds listen on')


_STATE_NAMES = {
    node.Instance.NOSTATE: 'pending',
    node.Instance.RUNNING: 'running',
    node.Instance.BLOCKED: 'blocked',
    node.Instance.PAUSED: 'paused',
    node.Instance.SHUTDOWN: 'shutdown',
    node.Instance.SHUTOFF: 'shutoff',
    node.Instance.CRASHED: 'crashed',
}

def _gen_key(user_id, key_name):
    try:
        manager = users.UserManager()
        private_key, fingerprint = manager.generate_key_pair(user_id, key_name)
    except Exception as ex:
        return {'exception': ex}
    return {'private_key': private_key, 'fingerprint': fingerprint}

class CloudController(object):
    def __init__(self):
        self.volumes = {}
        self.instances = {}
        self.network = network.NetworkController()

    def __str__(self):
        return 'CloudController'
    
    def setup(self):
        # Create keys folder, if it doesn't exist
        if not os.path.exists(FLAGS.keys_path):
            os.makedirs(os.path.abspath(FLAGS.keys_path))
        # Gen root CA, if we don't have one
        root_ca_path = os.path.join(FLAGS.ca_path, FLAGS.ca_file)
        if not os.path.exists(root_ca_path):
            start = os.getcwd()
            os.chdir(FLAGS.ca_path)
            runthis("Generating root CA: %s", "sh genrootca.sh")
            os.chdir(start)
            # TODO: Do this with M2Crypto instead

    def fetch_ca(self):
        return open(os.path.join(FLAGS.ca_path, 'cacert.pem')).read()
                          
    def _get_instance_by_ip(self, ip):
        if self.instances == {}:
            return None
        for node in self.instances.itervalues():
            for instance in node.itervalues():
                if instance['private_dns_name'] == ip:
                    return instance
        return None
         
    def get_metadata(self, ip):
        i = self._get_instance_by_ip(ip)
        if i is None:
            return None
        if i['key_name']:
            keys = {
                '0': {
                    '_name': i['key_name'],
                    'openssh-key': i['key_data']
                }
            }
        else:
            keys = ''
        data = {
            'user-data': base64.b64decode(i['user_data']),
            'meta-data': {
                'ami-id': i['image_id'],
                'ami-launch-index': i['ami_launch_index'],
                'ami-manifest-path': 'FIXME',
                'block-device-mapping': 'FIXME',
                'hostname': 'FIXME',
                'instance-id': i['instance_id'],
                'instance-type': i['instance_type'],
                'local-hostname': 'FIXME',
                'local-ipv4': 'FIXME',
                'placement': i['availability_zone'],
                'public-hostname': 'FIXME',
                'public-ipv4': 'FIXME',
                'public-keys' : keys,
                'reservation-id': i['reservation_id'],
                'security-groups': 'FIXME'
            }
        }
        return data
        

    def describe_key_pairs(self, context, key_name=None, **kwargs):
        key_pairs = []
        key_names = key_name and key_name or []
        if len(key_names) > 0:
            for key_name in key_names:
                key_pair = context.user.get_key_pair(key_name)
                if key_pair != None:
                    key_pairs.append({
                        'keyName': key_pair.name,
                        'keyFingerprint': key_pair.fingerprint,
                    })
        else:
            for key_pair in context.user.get_key_pairs():
                key_pairs.append({
                    'keyName': key_pair.name,
                    'keyFingerprint': key_pair.fingerprint,
                })

        return { 'keypairsSet': key_pairs }

    def create_key_pair(self, context, key_name, **kwargs):
        try:
            d = defer.Deferred()
            p = context.handler.application.settings.get('pool')
            def _complete(kwargs):
                if 'exception' in kwargs:
                    d.errback(kwargs['exception'])
                    return
                d.callback({'keyName': key_name,
                    'keyFingerprint': kwargs['fingerprint'],
                    'keyMaterial': kwargs['private_key']})
            p.apply_async(_gen_key, [context.user.id, key_name],
                callback=_complete)
            return d

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
        if self.volumes == {}:
            return {'volumeSet': [] } 
        volumes = []
        for storage in self.volumes.values():
            for volume in storage.values():
                if context.user.is_authorized(volume.get('user_id', None)):
                    v = copy.deepcopy(volume)
                    del v['user_id']
                    volumes.append(v)
        return defer.succeed({'volumeSet': volumes})

    def create_volume(self, context, size, **kwargs):
        calllib.cast('storage', {"method": "create_volume", 
                                 "args" : {"size": size,
                                           "user_id": context.user.id}})
        return defer.succeed(True)

    def _get_by_id(self, nodes, id):
        if nodes == {}:
            raise exception.ApiError("%s not found", id)
        for node in nodes.itervalues():
            if node.has_key(id):
                return node[id]
        raise exception.ApiError("%s not found", id)

    def _get_volume(self, volume_id):
        return self._get_by_id(self.volumes, volume_id)


    def _get_instance(self, instance_id):
        return self._get_by_id(self.instances, instance_id)


    def attach_volume(self, context, volume_id, instance_id, device, **kwargs):
        volume = self._get_volume(volume_id)
        if context.user.is_authorized(volume.get('user_id', None)):
            raise exception.ApiError("%s not authorized for %s", context.user.id, volume_id)
        instance = self._get_instance(instance_id)
        if context.user.is_authorized(instance.get('owner_id', None)):
            raise exception.ApiError("%s not authorized for %s", context.user.id, instance_id)
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
        # TODO(joshua): Make sure the updated state has been received first
        volume = self._get_volume(volume_id)
        if context.user.is_authorized(volume.get('user_id', None)):
            raise exception.ApiError("%s not authorized for %s", context.user.id, volume_id)
        instance_id = volume['instance_id']
        instance = self._get_instance(instance_id)
        if context.user.is_authorized(instance.get('owner_id', None)):
            raise exception.ApiError("%s not authorized for %s", context.user.id, instance_id)
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
        return defer.succeed(self.format_instances(context.user))

    def format_instances(self, user, reservation_id = None):
        if self.instances == {}:
            return {'reservationSet': []}
        reservations = {}
        for node in self.instances.values():
            for instance in node.values():
                res_id = instance.get('reservation_id', 'Unknown')
                if (user.is_authorized(instance.get('owner_id', None))
                    and (reservation_id == None or reservation_id == res_id)):
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
        # TODO: verify user has access to image
        
        kwargs['owner_id'] = context.user.id
        if kwargs.has_key('key_name'):
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
            (address, kwargs['network_name']) = self.network.allocate_address(str(kwargs['owner_id']), mac=str(kwargs['mac_address']))
            network = self.network.get_users_network(str(kwargs['owner_id']))
            kwargs['network_str'] = network.to_dict()
            kwargs['bridge_name'] = network.bridge_name
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
        return defer.succeed(self.format_instances(context.user,
                                                   kwargs['reservation_id']))
    
    def terminate_instances(self, context, instance_id, **kwargs):
        # TODO: return error if not authorized
        for i in instance_id:
            instance = self._get_instance(i)
            if context.user.is_authorized(instance.get('owner_id', None)):
                calllib.cast('node', {"method": "terminate_instance",
                              "args" : {"instance_id": i}})
        return defer.succeed(True)
        
    def delete_volume(self, context, volume_id, **kwargs):
        calllib.cast('storage', {"method": "delete_volume",
                                 "args" : {"volume_id": volume_id}})
        return defer.succeed(True)

    def describe_images(self, context, **kwargs):
        imageSet = images.list(context.user)
        
        return defer.succeed({'imagesSet': imageSet})
    
    def deregister_image(self, context, image_id, **kwargs):
        images.deregister(context.user, image_id)
                
        return defer.succeed({'imageId': image_id})
            
    def register_image(self, context, image_location, **kwargs):
        image_id = images.register(context.user, image_location)
        logging.debug("Registered %s as %s" % (image_location, image_id))
        
        return defer.succeed({'imageId': image_id})

    def update_state(self, topic, value):
        """ accepts status reports from the queue and consolidates them """
        # TODO(jmc): if an instance has disappeared from the node, call instance_death

        aggregate_state = getattr(self, topic)
        node_name = value.keys()[0]
        items = value[node_name]
        
        logging.debug("Updating %s state for %s" % (topic, node_name))

        for item_id in items.keys():
            if (aggregate_state.has_key('pending') and
                aggregate_state['pending'].has_key(item_id)):
                del aggregate_state['pending'][item_id]
        aggregate_state[node_name] = items

        return defer.succeed(True)
