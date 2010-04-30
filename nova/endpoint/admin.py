# vim: tabstop=4 shiftwidth=4 softtabstop=4
import contrib
import base64
from tornado import web

def user_dict(user, base64_file=None):
    if user:
        return {
            'username': user.id,
            'accesskey': user.access,
            'secretkey': user.secret,
            'file': base64_file,
        }
    else:
        return {}

def admin_only(target):
    def wrapper(*args, **kwargs):
        context = args[1]
        if context.user.is_admin():
            return target(*args, **kwargs)
        else:
            return {}

    return wrapper

class AdminController(object):
    def __init__(self, user_manager):
        self.user_manager = user_manager

    def __str__(self):
        return 'AdminController'
        
    @admin_only
    def describe_user(self, context, name, **kwargs):
        return user_dict(self.user_manager.get_user(name))

    @admin_only
    def describe_users(self, context, **kwargs):
        return {'userSet': [user_dict(u) for u in self.user_manager.get_users()] }

    @admin_only
    def register_user(self, context, name, **kwargs):
        self.user_manager.create_user(name)

        return user_dict(self.user_manager.get_user(name))
        
    @admin_only
    def deregister_user(self, context, name, **kwargs):
        self.user_manager.delete_user(name)

        return True
    
    @admin_only
    def generate_x509_for_user(self, context, name, **kwargs):
        user = self.user_manager.get_user(name)
        return user_dict(user, base64.b64encode(user.get_credentials()))
