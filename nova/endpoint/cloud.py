# vim: tabstop=4 shiftwidth=4 softtabstop=4
import os
import logging
import copy

from nova import contrib
import anyjson
import boto
import boto.s3
from twisted.internet import defer

from nova import rpc, crypto
import nova.flags
import flags
from nova.auth import users
import time
from nova.compute import node
from nova.compute import network
from nova import utils, exception
from nova.utils import runthis, generate_uid
from nova import crypto
import images
import base64
import tornado
from nova.cloudpipe.pipelib import CloudPipe

FLAGS = flags.FLAGS

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
        self.pipe = CloudPipe(self)
        self.setup()

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
                          
    def get_instance_by_ip(self, ip):
        if self.instances == {}:
            return None
        for node in self.instances.itervalues():
            for instance in node.itervalues():
                if instance['private_dns_name'] == ip:
                    return instance
        return None

    def get_metadata(self, ip):
        i = self.get_instance_by_ip(ip)
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
                'ami-manifest-path': 'FIXME', # image property
                'block-device-mapping': { # TODO: replace with real data
                    'ami': 'sda1',
                    'ephemeral0': 'sda2',
                    'root': '/dev/sda1',
                    'swap': 'sda3'
                },
                'hostname': i['private_dns_name'], # is this public sometimes?
                'instance-action': 'none',
                'instance-id': i['instance_id'],
                'instance-type': i['instance_type'],
                'local-hostname': i['private_dns_name'],
                'local-ipv4': i['private_dns_name'], # TODO: switch to IP
                'kernel-id': i['kernel_id'],
                'placement': {
                    'availaibility-zone': i['availability_zone'],
                },
                'public-hostname': i['dns_name'],
                'public-ipv4': i['dns_name'], # TODO: switch to IP
                'public-keys' : keys,
                'ramdisk-id': i['ramdisk_id'],
                'reservation-id': i['reservation_id'],
                'security-groups': i['groups']
            }
        }
        if False: # TODO: store ancestor ids
            data['ancestor-ami-ids'] = []
        if i['product_codes']:
            data['product-codes'] = i['product_codes']
        return data


    def describe_availability_zones(self, context, **kwargs):
        return {'availabilityZoneInfo': [{'zoneName': 'nova', 'zoneState': 'available'}]}

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
        return True

    def delete_security_group(self, context, group_name, **kwargs):
        return True

    def get_console_output(self, context, instance_id, **kwargs):
        # instance_id is passed in as a list of instances
        node, instance = self._get_instance(instance_id[0])
        if node == 'pending':
            raise exception.ApiError('Cannot get output for pending instance')
        if not context.user.is_authorized(instance.get('owner_id', None)):
            raise exception.ApiError('Not authorized to view output')
        return rpc.call('%s.%s' % (FLAGS.compute_topic, node),
            {"method": "get_console_output",
             "args" : {"instance_id": instance_id[0]}})

    def _get_user_id(self, context):
        if context and context.user:
            return context.user.id
        else:
            return None

    def describe_volumes(self, context, **kwargs):
        if self.volumes == {}:
            return {'volumeSet': [] }
        volumes = []
        for node_name, node in self.volumes.iteritems():
            for volume in node.values():
                if context.user.is_authorized(volume.get('user_id', None)):
                    v = copy.deepcopy(volume)
                    if context.user.is_admin():
                        v['status'] = '%s (%s, %s, %s, %s)' % (v.get('status', None),
                            v['user_id'], node_name, v.get('instance_id', ''), v.get('mountpoint', ''))
                    del v['user_id']
                    volumes.append(v)
        return defer.succeed({'volumeSet': volumes})

    def create_volume(self, context, size, **kwargs):
        d = rpc.call(FLAGS.storage_topic, {"method": "create_volume",
                                 "args" : {"size": size,
                                           "user_id": context.user.id}})
        return d

    def _get_by_id(self, nodes, id):
        if nodes == {}:
            raise exception.NotFound("%s not found" % id)
        for node_name, node in nodes.iteritems():
            if node.has_key(id):
                return node_name, node[id]
        raise exception.NotFound("%s not found" % id)

    def _get_volume(self, volume_id):
        return self._get_by_id(self.volumes, volume_id)


    def _get_instance(self, instance_id):
        return self._get_by_id(self.instances, instance_id)


    def attach_volume(self, context, volume_id, instance_id, device, **kwargs):
        storage_node, volume = self._get_volume(volume_id)
        # TODO: (joshua) Fix volumes to store creator id
        if not context.user.is_authorized(volume.get('user_id', None)):
           raise exception.ApiError("%s not authorized for %s" % (context.user.id, volume_id))
        compute_node, instance = self._get_instance(instance_id)
        if not context.user.is_authorized(instance.get('owner_id', None)):
            raise exception.ApiError(message="%s not authorized for %s" % (context.user.id, instance_id))
        aoe_device = volume['aoe_device']
        # Needs to get right node controller for attaching to
        # TODO: Maybe have another exchange that goes to everyone?
        rpc.cast('%s.%s' % (FLAGS.compute_topic, compute_node),
                                {"method": "attach_volume",
                                 "args" : {"aoe_device": aoe_device,
                                           "instance_id" : instance_id,
                                           "mountpoint" : device}})
        rpc.cast('%s.%s' % (FLAGS.storage_topic, storage_node),
                                {"method": "attach_volume",
                                 "args" : {"volume_id": volume_id,
                                           "instance_id" : instance_id,
                                           "mountpoint" : device}})
        return defer.succeed(True)

    def detach_volume(self, context, volume_id, **kwargs):
        # TODO(joshua): Make sure the updated state has been received first
        storage_node, volume = self._get_volume(volume_id)
        if not context.user.is_authorized(volume.get('user_id', None)):
            raise exception.ApiError("%s not authorized for %s" % (context.user.id, volume_id))
        instance = None
        if volume.has_key('instance_id'):
            instance_id = volume['instance_id']
            try:
                compute_node, instance = self._get_instance(instance_id)
                mountpoint = volume['mountpoint']
                if not context.user.is_authorized(instance.get('owner_id', None)):
                    raise exception.ApiError("%s not authorized for %s" % (context.user.id, instance_id))
                rpc.cast('%s.%s' % (FLAGS.compute_topic, compute_node),
                                {"method": "detach_volume",
                                 "args" : {"instance_id": instance_id,
                                           "mountpoint": mountpoint}})
            except exception.NotFound:
                pass
        rpc.cast('%s.%s' % (FLAGS.storage_topic, storage_node),
                                {"method": "detach_volume",
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
        for node_name, node in self.instances.iteritems():
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
                    i['public_dns_name'] = self.network.get_public_ip_for_instance(i['instance_id'])
                    i['private_dns_name'] = instance.get('private_dns_name', None)
                    if not i['public_dns_name']:
                        i['public_dns_name'] = i['private_dns_name']
                    i['dns_name'] = instance.get('dns_name', None)
                    i['key_name'] = instance.get('key_name', None)
                    if user.is_admin():
                        i['key_name'] = '%s (%s, %s)' % (i['key_name'],
                            instance.get('owner_id', None), node_name)
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

    def describe_addresses(self, context, **kwargs):
        return self.format_addresses(context.user)

    def format_addresses(self, user):
        addresses = []
        # TODO(vish): move authorization checking into network.py
        for address_record in self.network.describe_addresses(type=network.PublicNetwork):
            #logging.debug(address_record)
            if user.is_authorized(address_record[u'user_id']):
                address = {
                    'public_ip': address_record[u'address'],
                    'instance_id' : address_record.get(u'instance_id', 'free')
                }
                # FIXME: add another field for user id
                if user.is_admin():
                    address['instance_id'] = "%s (%s)" % (
                        address['instance_id'],
                        address_record[u'user_id'],
                    )
                addresses.append(address)
        # logging.debug(addresses)
        return {'addressesSet': addresses}

    def allocate_address(self, context, **kwargs):
        # TODO: Verify user is valid?
        kwargs['owner_id'] = context.user.id
        (address,network_name) = self.network.allocate_address(context.user.id, type=network.PublicNetwork)
        return defer.succeed({'addressSet': [{'publicIp' : address}]})

    def release_address(self, context, **kwargs):
        self.network.deallocate_address(kwargs.get('public_ip', None))
        return defer.succeed({'releaseResponse': ["Address released."]})

    def associate_address(self, context, instance_id, **kwargs):
        node, instance = self._get_instance(instance_id)
        rv = self.network.associate_address(kwargs['public_ip'], instance['private_dns_name'], instance_id)
        return defer.succeed({'associateResponse': ["Address associated."]})

    def disassociate_address(self, context, **kwargs):
        rv = self.network.disassociate_address(kwargs['public_ip'])
        # TODO - Strip the IP from the instance
        return rv

    def run_instances(self, context, **kwargs):
        # passing all of the kwargs on to node.py
        logging.debug("Going to run instances...")
        # logging.debug(kwargs)
        # TODO: verify user has access to image
        launchstate = self._create_reservation(context.user, kwargs)
        pending = {}
        for num in range(int(launchstate['max_count'])):
            launchstate['mac_address'] = utils.generate_mac()
            (address, launchstate['network_name']) = self.network.allocate_address(str(launchstate['owner_id']), mac=str(launchstate['mac_address']))
            launchstate['private_dns_name'] = str(address)
            launchstate = self._really_run_instance(context.user, kwargs, num)
            pending[kwargs['instance_id']] = dict(launchstate)
            pending[kwargs['instance_id']]['state'] = node.Instance.NOSTATE
        # TODO(vish): pending instances will be lost on crash
        if(not self.instances.has_key('pending')):
            self.instances['pending'] = {}
        self.instances['pending'].update(pending)
        return defer.succeed(self.format_instances(context.user, launchstate['reservation_id']))

    def _create_reservation(self, user, launchstate):
        launchstate['owner_id'] = user.id
        launchstate['reservation_id'] = generate_uid('r')
        launchstate['launch_time'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        if launchstate.has_key('key_name'):
            key_pair = user.get_key_pair(launchstate['key_name'])
            if not key_pair:
                raise exception.ApiError('Key Pair %s not found' %
                                         launchstate['key_name'])
            launchstate['key_data'] = key_pair.public_key
        return launchstate

    def _really_run_instance(self, user, launchstate, idx):
        launchstate['instance_id'] = generate_uid('i')
        launchstate['ami_launch_index'] = idx 
        network = self.network.get_users_network(str(user.id))
        launchstate['network_str'] = network.to_dict()
        launchstate['bridge_name'] = network.bridge_name
        logging.debug("Casting to node for %s's instance with IP of %s in the %s network" %
                      (user.name,
                       launchstate['private_dns_name'],
                       launchstate['network_name']))
        rpc.call(FLAGS.compute_topic, 
                              {"method": "run_instance", 
                               "args" : launchstate 
                                        })
        return launchstate

    def run_vpn_instance(self, user, **kwargs):
        kwargs['image_id'] = FLAGS.vpn_image_id
        kwargs['owner_id'] = user.id
        launchstate = self._create_reservation(user, kwargs)
        launchstate['mac_address'] = utils.generate_mac()
        (address, launchstate['network_name']) = self.network.get_cloudpipe_address(str(launchstate['owner_id']), mac=str(launchstate['mac_address']))
        launchstate['private_dns_name'] = str(address)
        pending = {}
        launchstate = self._really_run_instance(user, kwargs, 0)
        pending[kwargs['instance_id']] = dict(launchstate)
        pending[kwargs['instance_id']]['state'] = node.Instance.NOSTATE
        # TODO(vish): pending instances will be lost on crash
        if(not self.instances.has_key('pending')):
            self.instances['pending'] = {}
        self.instances['pending'].update(pending)
    
    def terminate_instances(self, context, instance_id, **kwargs):
        # TODO: return error if not authorized
        for i in instance_id:
            node, instance = self._get_instance(i)
            if node == 'pending':
                raise exception.ApiError('Cannot terminate pending instance')
            if context.user.is_authorized(instance.get('owner_id', None)):
                rpc.cast('%s.%s' % (FLAGS.compute_topic, node),
                             {"method": "terminate_instance",
                              "args" : {"instance_id": i}})
            try:
                self.network.disassociate_address(instance.get('public_dns_name', 'bork'))
            except:
                pass
        return defer.succeed(True)

    def reboot_instances(self, context, instance_id, **kwargs):
        # TODO: return error if not authorized
        for i in instance_id:
            node, instance = self._get_instance(i)
            if node == 'pending':
                raise exception.ApiError('Cannot reboot pending instance')
            if context.user.is_authorized(instance.get('owner_id', None)):
                rpc.cast('%s.%s' % (FLAGS.node_topic, node),
                             {"method": "reboot_instance",
                              "args" : {"instance_id": i}})
        return defer.succeed(True)

    def delete_volume(self, context, volume_id, **kwargs):
        # TODO: return error if not authorized
        storage_node, volume = self._get_volume(volume_id)
        if context.user.is_authorized(volume.get('user_id', None)):
            rpc.cast('%s.%s' % (FLAGS.storage_topic, storage_node),
                                {"method": "delete_volume",
                                 "args" : {"volume_id": volume_id}})
        return defer.succeed(True)

    def describe_images(self, context, image_id=None, **kwargs):
        imageSet = images.list(context.user)
        if not image_id is None:
            imageSet = [i for i in imageSet if i['imageId'] in image_id]

        return defer.succeed({'imagesSet': imageSet})

    def deregister_image(self, context, image_id, **kwargs):
        images.deregister(context.user, image_id)

        return defer.succeed({'imageId': image_id})

    def register_image(self, context, image_location=None, **kwargs):
        if image_location is None and kwargs.has_key('name'):
            image_location = kwargs['name']

        image_id = images.register(context.user, image_location)
        logging.debug("Registered %s as %s" % (image_location, image_id))

        return defer.succeed({'imageId': image_id})

    def cloudcron(self):
        logging.debug("Cloud Cron")
        self.ensure_VPN_connections()

    def ensure_VPN_connections(self):
        um = users.UserManager()
        user_list = um.get_users()
        for user in user_list:
		    logging.debug("Checking user -%s-" % (user.name))
		    if not self.is_vpn_running(user.name):
			    logging.debug("Not running for user -%s-" % (user.name))
			    self.pipe.launch_vpn_instance(user.name)

    def is_vpn_running(self, username):
        if self.vpn_running_instance(username):
            return True
        return False

    def vpn_running_instance(self, username):
        for node_name, nodeobj in self.instances.iteritems():
            for instance in nodeobj.values():
                if (instance['image_id'] == FLAGS.vpn_image_id
                    and instance['state'] in [node.Instance.NOSTATE, node.Instance.RUNNING]
                    and instance['owner_id'] == username):
                    return instance
        return None

    def modify_image_attribute(self, context, image_id, attribute, operation_type, **kwargs):
        if attribute != 'launchPermission':
            raise exception.ApiError('only launchPermission is supported')
        if len(kwargs['user_group']) != 1 and kwargs['user_group'][0] != 'all':
            raise exception.ApiError('only group "all" is supported')
        if not operation_type in ['add', 'delete']:
            raise exception.ApiError('operation_type must be add or delete')

        result = images.modify(context.user, image_id, operation_type)

        return defer.succeed(result)

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
