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
        
    def describe_user(self, request_id, **kwargs):
        # TODO: This doesn't work
        username = kwargs['Name'][0]
        user = self.users.get_user(username)
        return {
            'id': user.id,
            'access': user.access,
            'secret': user.secret
        }

    def register_user(self, request_id, **kwargs):
        username = kwargs['Name'][0]
        return anyjson.serialize(self.user_manager.create_user(username))
        
    def deregister_user(self, request_id, **kwargs):
        username = kwargs['Name'][0]
        return anyjson.serialize(self.user_manager.delete_user(username))



