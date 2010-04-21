#!/usr/bin/python
# vim: tabstop=4 shiftwidth=4 softtabstop=4
import logging
import random
import re

# TODO(termie): replace minidom with etree
from xml.dom import minidom

import contrib
import tornado.web
from twisted.internet import defer

import cloud
import exception
import flags
import utils


FLAGS = flags.FLAGS
flags.DEFINE_integer('cc_port', 8773, 'cloud controller port')


_c2u = re.compile('(((?<=[a-z])[A-Z])|([A-Z](?![A-Z]|$)))')


def _camelcase_to_underscore(str):
    return _c2u.sub(r'_\1', str).lower().strip('_')


def _underscore_to_camelcase(str):
    return ''.join([x[:1].upper() + x[1:] for x in str.split('_')])


def _underscore_to_xmlcase(str):
    res = _underscore_to_camelcase(str)
    return res[:1].lower() + res[1:]


class APIRequestContext(object):
    def __init__(self, user):
        self.user = user
        self.request_id = ''.join(
                [random.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890-')
                 for x in xrange(20)]
                )


class APIRequest(object):
    def __init__(self, controller, action):
        self.controller = controller
        self.action = action
        
    def send(self, user, **kwargs):
        context = APIRequestContext(user)
    
        try:
            method = getattr(self.controller,
                             _camelcase_to_underscore(self.action))
        except AttributeError:
            _error = ('Unsupported API request: controller = %s,'
                      'action = %s') % (self.controller, self.action)
            logging.warning(_error)
            # TODO: Raise custom exception, trap in apiserver,
            #       and reraise as 400 error.
            raise Exception(_error)
        
        args = {}
        for key, value in kwargs.items():
            parts = key.split(".")
            key = _camelcase_to_underscore(parts[0])
            if len(parts) > 1:
                d = args.get(key, {})
                d[parts[1]] = value[0]
                value = d
            else:
                value = value[0]
            args[key] = value
            
        for key in args.keys():
            if isinstance(args[key], dict):
                if args[key] != {} and args[key].keys()[0].isdigit():
                    s = args[key].items()
                    s.sort()
                    args[key] = [v for k, v in s]

        d = defer.maybeDeferred(method, context, **args)
        d.addCallback(self._render_response, context.request_id)
        return d

    def _render_response(self, response_data, request_id):
        xml = minidom.Document()
    
        response_el = xml.createElement(self.action + 'Response')
        response_el.setAttribute('xmlns',
                                 'http://ec2.amazonaws.com/doc/2009-11-30/')
        request_id_el = xml.createElement('requestId')
        request_id_el.appendChild(xml.createTextNode(request_id))
        response_el.appendChild(request_id_el)
        if(response_data == True):
            self._render_dict(xml, response_el, {'return': 'true'})
        else: 
            self._render_dict(xml, response_el, response_data)
    
        xml.appendChild(response_el)
    
        response = xml.toxml()
        xml.unlink()
        logging.debug(response)
        return response
    
    def _render_dict(self, xml, el, data):
        try:
            for key in data.keys():
                val = data[key]
                el.appendChild(self._render_data(xml, key, val))
        except:
            logging.debug(data)
            raise

    def _render_data(self, xml, el_name, data):
        el_name = _underscore_to_xmlcase(el_name)
        data_el = xml.createElement(el_name)
    
        if isinstance(data, list):
            for item in data:
                data_el.appendChild(self._render_data(xml, 'item', item))
        elif isinstance(data, dict):
            self._render_dict(xml, data_el, data)
        elif hasattr(data, '__dict__'):
            self._render_dict(xml, data_el, data.__dict__)
        elif data != None:
            data_el.appendChild(xml.createTextNode(str(data)))
        
        return data_el


class RootRequestHandler(tornado.web.RequestHandler):
    def get(self):
        self.write('listening')


class APIRequestHandler(tornado.web.RequestHandler):
    def get(self, controller_name):
        self.execute(controller_name)
    
    @tornado.web.asynchronous
    def execute(self, controller_name):
        # Obtain the appropriate controller for this request.
        try:
            controller = self.application.controllers[controller_name]
        except KeyError:
            self._error('unhandled', 'no controller named %s' % controller_name)
            return
        
        args = self.request.arguments
        
        # Read request signature.
        try:
            signature = args.pop('Signature')[0]
        except:
            raise Tornado.web.HTTPError(400)
            
        # Make a copy of args for authentication and signature verification.
        auth_params = {} 
        for key, value in args.items():
            auth_params[key] = value[0]

        # Get requested action and remove authentication args for final request.
        try:
            action = args.pop('Action')[0]
            args.pop('AWSAccessKeyId')
            args.pop('SignatureMethod')
            args.pop('SignatureVersion')
            args.pop('Version')
            args.pop('Timestamp')
        except:
            raise tornado.web.HTTPError(400)

        # Authenticate the request.
        user = self.application.user_manager.authenticate(
            auth_params,
            signature,
            self.request.method,
            self.request.host,
            self.request.path
        )
        
        if not user:
            raise tornado.web.HTTPError(403)

        logging.debug('action: %s' % action)

        for key, value in args.items():
            logging.debug('arg: %s\t\tval: %s' % (key, value))

        request = APIRequest(controller, action)
        d = request.send(user, **args)
        d.addCallback(utils.debug)

        # TODO: Wrap response in AWS XML format  
        d.addCallbacks(self._write_callback, self._error_callback)

    def _write_callback(self, data): 
        self.set_header('Content-Type', 'text/xml')
        self.write(data)
        self.finish()

    def _error_callback(self, failure):
        try:
            failure.raiseException()
        except exception.ApiError as ex:
            self._error(type(ex).__name__ + "." + ex.code, ex.message)
        # TODO(vish): do something more useful with unknown exceptions
        except Exception as ex:
            self._error(type(ex).__name__, str(ex))
            raise

    def post(self, controller_name):
        self.execute(controller_name)

    def _error(self, code, message):
        self._status_code = 400
        self.set_header('Content-Type', 'text/xml')
        self.write('<?xml version="1.0"?>\n')
        self.write('<Response><Errors><Error><Code>%s</Code>'
                   '<Message>%s</Message></Error></Errors>'
                   '<RequestID>?</RequestID></Response>' % (code, message))
        self.finish()


class APIServerApplication(tornado.web.Application):
    def __init__(self, user_manager, controllers):
        tornado.web.Application.__init__(self, [
            (r'/', RootRequestHandler),
            (r'/services/([A-Za-z0-9]+)/', APIRequestHandler),
        ])
        self.user_manager = user_manager
        self.controllers = controllers
