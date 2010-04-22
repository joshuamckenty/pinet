# vim: tabstop=4 shiftwidth=4 softtabstop=4
import logging
import random

import contrib
import anyjson

import flags
import users

FLAGS = flags.FLAGS
flags.DEFINE_string('admin_topic', 'admin', 'the topic admin listens on')

_log = logging.getLogger()
        
class AdminController(object):
    def __init__(self, user_manager):
        self.users = user_manager

    def __str__(self):
        return 'AdminController'
        
    def describe_user(self, context, **kwargs):
        username = kwargs['name']

        return self._get_dict(self.users.get_user(username))

    def register_user(self, context, **kwargs):
        username = kwargs['name']
        self.users.create_user(username)

        return self._get_dict(self.users.get_user(username))
        
    def deregister_user(self, context, **kwargs):
        username = kwargs['name']
        
        self.users.delete_user(username)
        
        return {}

    def _get_dict(self, user):
        if user:
            # TODO: Need to return code for credentials download
            return {
                'username': user.id,
                'code': 'blank',
                'accesskey': user.access,
                'secretkey': user.secret
            }
        else:
            return {}



