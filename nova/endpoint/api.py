#!/usr/bin/python
# vim: tabstop=4 shiftwidth=4 softtabstop=4
import logging
import random
import re

# TODO(termie): replace minidom with etree
from xml.dom import minidom

from nova import contrib, exception, utils, crypto
import tornado.web
from twisted.internet import defer

import cloud
import flags
import multiprocessing

from nova.cloudpipe.pipelib import CloudPipe
import urllib
import logging


_log = logging.getLogger("api")
_log.setLevel(logging.WARN)


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
    def __init__(self, handler, user):
        self.handler = handler
        self.user = user
        self.request_id = ''.join(
                [random.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890-')
                 for x in xrange(20)]
                )


class APIRequest(object):
    def __init__(self, handler, controller, action):
        self.handler = handler
        self.controller = controller
        self.action = action

    def send(self, user, **kwargs):
        context = APIRequestContext(self.handler, user)

        try:
            method = getattr(self.controller,
                             _camelcase_to_underscore(self.action))
        except AttributeError:
            _error = ('Unsupported API request: controller = %s,'
                      'action = %s') % (self.controller, self.action)
            _log.warning(_error)
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
        _log.debug(response)
        return response

    def _render_dict(self, xml, el, data):
        try:
            for key in data.keys():
                val = data[key]
                el.appendChild(self._render_data(xml, key, val))
        except:
            _log.debug(data)
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
        elif isinstance(data, bool):
            data_el.appendChild(xml.createTextNode(str(data).lower()))
        elif data != None:
            data_el.appendChild(xml.createTextNode(str(data)))

        return data_el


class RootRequestHandler(tornado.web.RequestHandler):
    def get(self):
        # available api versions
        versions = [
            '1.0',
            '2007-01-19',
            '2007-03-01',
            '2007-08-29',
            '2007-10-10',
            '2007-12-15',
            '2008-02-01',
            '2008-09-01',
            '2009-04-04',
        ]
        for version in versions:
            self.write('%s\n' % version)
        self.finish()

class MetadataRequestHandler(tornado.web.RequestHandler):
    def print_data(self, data):
        if isinstance(data, dict):
            output = ''
            for key in data:
                if key == '_name':
                    continue
                output += key
                if isinstance(data[key], dict):
                    if '_name' in data[key]:
                        output += '=' + str(data[key]['_name'])
                    else:
                        output += '/'
                output += '\n'
            self.write(output[:-1]) # cut off last \n
        elif isinstance(data, list):
            self.write('\n'.join(data))
        else:
            self.write(str(data))

    def lookup(self, path, data):
        items = path.split('/')
        for item in items:
            if item:
                if not isinstance(data, dict):
                    return data
                if not item in data:
                    return None
                data = data[item]
        return data

    def get(self, path):
        cc = self.application.controllers['Cloud']
        meta_data = cc.get_metadata(self.request.remote_ip)
        if meta_data is None:
            _log.error('Failed to get metadata for ip: %s' %
                        self.request.remote_ip)
            raise tornado.web.HTTPError(404)
        data = self.lookup(path, meta_data)
        if data is None:
            raise tornado.web.HTTPError(404)
        self.print_data(data)
        self.finish()

class CloudPipeRequestHandler(tornado.web.RequestHandler):
    def get(self, path):
        self.manager = UserManager()
        self.pipe = CloudPipe()
        #if str(self.path) == u"/favicon.ico":
        #    self.printCustomHTTPResponse(204)
        #    return
        if path[:7] == "/getca/":
            self.send_root_ca()
        elif path[:9] == "/getcert/":
            _log.debug( "Getting zip for %s" % (path[9:]))
            try:
                self.send_signed_zip(self.path[9:])
            except Exception, err:
                _log.debug('ERROR: %s\n' % str(err))
                raise tornado.web.HTTPError(404)
        self.finish()
        
    def get_username_from_ip(self, ip):
        cc = self.application.controllers['Cloud']
        instance = cc.get_instance_by_ip(ip)
        return instance['owner_id']

    def send_root_ca(self):
        username = self.get_username_from_ip(self.request.remote_ip)
        self.set_header("Content-Type", "text/plain")
        self.write(crypto.fetch_ca(username))

    def send_signed_zip(self, username):
        self.set_header("Content-Type", "application/zip")
        self.write(self.manager.get_signed_zip(username))

    def post(self, path):
        username = self.get_username_from_ip(self.request.remote_ip)
        cert = self.get_argument('cert', '')
        self.write(self.manager.sign_cert(urllib.unquote(cert), username))
        self.finish()

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
            raise tornado.web.HTTPError(400)

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

        _log.debug('action: %s' % action)

        for key, value in args.items():
            _log.debug('arg: %s\t\tval: %s' % (key, value))

        request = APIRequest(self, controller, action)
        d = request.send(user, **args)
        # d.addCallback(utils.debug)

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
            (r'/cloudpipe/(.*)', CloudPipeRequestHandler),
            (r'/services/([A-Za-z0-9]+)/', APIRequestHandler),
            (r'/latest/([-A-Za-z0-9/]*)', MetadataRequestHandler),
            (r'/2009-04-04/([-A-Za-z0-9/]*)', MetadataRequestHandler),
            (r'/2008-09-01/([-A-Za-z0-9/]*)', MetadataRequestHandler),
            (r'/2008-02-01/([-A-Za-z0-9/]*)', MetadataRequestHandler),
            (r'/2007-12-15/([-A-Za-z0-9/]*)', MetadataRequestHandler),
            (r'/2007-10-10/([-A-Za-z0-9/]*)', MetadataRequestHandler),
            (r'/2007-08-29/([-A-Za-z0-9/]*)', MetadataRequestHandler),
            (r'/2007-03-01/([-A-Za-z0-9/]*)', MetadataRequestHandler),
            (r'/2007-01-19/([-A-Za-z0-9/]*)', MetadataRequestHandler),
            (r'/1.0/([-A-Za-z0-9/]*)', MetadataRequestHandler),
        ], pool=multiprocessing.Pool(4))
        self.user_manager = user_manager
        self.controllers = controllers
