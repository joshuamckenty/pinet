#!/usr/bin/env python
#
# Copyright 2009 Facebook
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

"""Implementation of an S3-like storage server based on local files.

Useful to test features that will eventually run on S3, or if you want to
run something locally that was once running on S3.

We don't support all the features of S3, but it does work with the
standard S3 client for the most basic semantics. To use the standard
S3 client with this module:

    c = S3.AWSAuthConnection("", "", server="localhost", port=8888,
                             is_secure=False)
    c.create_bucket("mybucket")
    c.put("mybucket", "mykey", "a value")
    print c.get("mybucket", "mykey").body

"""

import nova.contrib
from nova import crypto
from nova import utils


import datetime
import shutil
from tornado import escape
import os
import urllib

from tornado import web
import glob
import anyjson
import logging
import flags
import multiprocessing

FLAGS = flags.FLAGS

# flags.DEFINE_string('buckets_path', utils.abspath('../buckets'), 'path to s3 buckets')
# flags.DEFINE_string('images_path', utils.abspath('../images'), 'path to decrypted images')

logging.getLogger("s3").setLevel(logging.DEBUG)

class Application(web.Application):
    """Implementation of an S3-like storage server based on local files.

    If bucket depth is given, we break files up into multiple directories
    to prevent hitting file system limits for number of files in each
    directories. 1 means one level of directories, 2 means 2, etc.
    """
    def __init__(self, user_manager):
        web.Application.__init__(self, [
            (r"/", RootHandler),
            (r"/_images/", ImageHandler),
            (r"/([^/]+)/(.+)", ObjectHandler),
            (r"/([^/]+)/", BucketHandler),
        ])
        self.directory = os.path.abspath(FLAGS.buckets_path)
        if not os.path.exists(self.directory):
            os.makedirs(self.directory)
        if not os.path.exists(FLAGS.images_path):
            raise "ERROR: images path does not exist"
        self.user_manager = user_manager


class BaseRequestHandler(web.RequestHandler):
    SUPPORTED_METHODS = ("PUT", "GET", "DELETE", "HEAD")
    
    @property    
    def user(self):
        if not hasattr(self, '_user'):
            try:
                access = self.request.headers['Authorization'].split(' ')[1].split(':')[0]
                user = self.application.user_manager.get_user_from_access_key(access)
                user.secret # FIXME: check signature here!
                self._user = user
            except:
                raise web.HTTPError(403)
        return self._user

    def render_xml(self, value):
        assert isinstance(value, dict) and len(value) == 1
        self.set_header("Content-Type", "application/xml; charset=UTF-8")
        name = value.keys()[0]
        parts = []
        parts.append('<' + escape.utf8(name) +
                     ' xmlns="http://doc.s3.amazonaws.com/2006-03-01">')
        self._render_parts(value.values()[0], parts)
        parts.append('</' + escape.utf8(name) + '>')
        self.finish('<?xml version="1.0" encoding="UTF-8"?>\n' +
                    ''.join(parts))

    def _render_parts(self, value, parts=[]):
        if isinstance(value, basestring):
            parts.append(escape.xhtml_escape(value))
        elif isinstance(value, int) or isinstance(value, long):
            parts.append(str(value))
        elif isinstance(value, datetime.datetime):
            parts.append(value.strftime("%Y-%m-%dT%H:%M:%S.000Z"))
        elif isinstance(value, dict):
            for name, subvalue in value.iteritems():
                if not isinstance(subvalue, list):
                    subvalue = [subvalue]
                for subsubvalue in subvalue:
                    parts.append('<' + escape.utf8(name) + '>')
                    self._render_parts(subsubvalue, parts)
                    parts.append('</' + escape.utf8(name) + '>')
        else:
            raise Exception("Unknown S3 value type %r", value)

    def head(self, *args, **kwargs):
        return self.get(*args, **kwargs) 

class RootHandler(BaseRequestHandler):
    def get(self):
        buckets = [b for b in Bucket.all() if b.is_authorized(self.user)]

        self.render_xml({"ListAllMyBucketsResult": {
            "Buckets": {"Bucket": [b.to_json() for b in buckets]},
        }})

class BucketHandler(BaseRequestHandler):
    def get(self, bucket_name):
        logging.debug("List keys for bucket %s" % (bucket_name))
        
        bucket = Bucket(bucket_name)
        
        if not bucket.is_authorized(self.user):
            raise web.HTTPError(403)
        
        prefix = self.get_argument("prefix", u"")
        marker = self.get_argument("marker", u"")
        max_keys = int(self.get_argument("max-keys", 1000))
        terse = int(self.get_argument("terse", 0))

        results = bucket.list_keys(prefix=prefix, marker=marker, max_keys=max_keys, terse=terse)
        self.render_xml({"ListBucketResult": results})

    def put(self, bucket_name):
        Bucket.create(bucket_name, self.user)
        self.finish()

    def delete(self, bucket_name):
        bucket = Bucket(bucket_name)
        
        if bucket.is_authorized(self.user):
            raise web.HTTPError(403)

        bucket.delete()
        self.set_status(204)
        self.finish()

class ObjectHandler(BaseRequestHandler):
    def get(self, bucket_name, object_name):
        bucket = Bucket(bucket_name)
        
        if not bucket.is_authorized(self.user):
            raise web.HTTPError(403)
        
        obj = bucket[urllib.unquote(object_name)]
        self.set_header("Content-Type", "application/unknown")
        self.set_header("Last-Modified", datetime.datetime.utcfromtimestamp(obj.mtime))
        self.set_header("Etag", '"' + obj.md5 + '"')
        self.finish(obj.read())

    def put(self, bucket_name, object_name):
        bucket = Bucket(bucket_name)
        
        if not bucket.is_authorized(self.user):
            raise web.HTTPError(403)
        
        key = urllib.unquote(object_name)
        bucket[key] = self.request.body
        self.set_header("Etag", '"' + bucket[key].md5 + '"')
        self.finish()

    def delete(self, bucket_name, object_name):
        bucket = Bucket(bucket_name)
        
        if not bucket.is_authorized(self.user):
            raise web.HTTPError(403)
        
        del bucket[urllib.unquote(object_name)]
        self.set_status(204)
        self.finish()

class ImageHandler(BaseRequestHandler):
    SUPPORTED_METHODS = ("POST", "PUT", "GET", "DELETE")
    
    def get(self):
        """ returns a json listing of all images 
            that a user has permissions to see """

        images = [i for i in Image.all() if i.is_authorized(self.user)]

        self.finish(anyjson.serialize([i.json for i in images]))

    def put(self):
        """ create a new registered image """
        
        image_id       = self.get_argument('image_id',       u'')
        image_location = self.get_argument('image_location', u'')

        image_path = os.path.join(FLAGS.images_path, image_id)
        if not image_path.startswith(FLAGS.images_path) or \
           os.path.exists(image_path):
            raise web.HTTPError(403)
        
        
        bucket = Bucket(image_location.split("/")[0])
        
        if not bucket.is_authorized(self.user):
            raise web.HTTPError(403)

        p = multiprocessing.Process(target=Image.create,args=
            (image_id, image_location, self.user))
        p.start()        
        self.finish()

    def post(self):
        """ update image attributes """
        pass

    def delete(self):
        """ delete a registered image """
        image_id = self.get_argument("image_id", u"")
        image = Image(image_id)

        if image.owner_id != self.user.id:
            raise web.HTTPError(403)

        image.delete()

        self.set_status(204)
