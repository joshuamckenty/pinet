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

import base64
import bisect
import datetime
import tarfile
import tempfile
import shutil
from tornado import escape
import hashlib
from tornado import httpserver
import os
import os.path
import urllib
from hashlib import sha1 as sha
from M2Crypto import BN, EVP, RSA, util, Rand, m2, X509
from binascii import hexlify, unhexlify

from tornado import web
import crypto
import glob
import stat
import anyjson
import xml.etree
from xml.etree import ElementTree
import logging
import flags
import utils

FLAGS = flags.FLAGS

flags.DEFINE_string('buckets_path', utils.abspath('../buckets'), 'path to s3 buckets')
flags.DEFINE_string('images_path', utils.abspath('../images'), 'path to decrypted images')

logging.getLogger().setLevel(logging.DEBUG)
logging.getLogger("tornado.web").setLevel(logging.DEBUG)

# Got these from Euca2ools, will need to revisit them
IMAGE_IO_CHUNK = 10 * 1024
IMAGE_SPLIT_CHUNK = IMAGE_IO_CHUNK * 1024;


class Bucket(object):
    def __init__(self, name):
        self.name = name
        self.path = os.path.abspath(os.path.join(FLAGS.buckets_path, name))
        if not self.path.startswith(os.path.abspath(FLAGS.buckets_path)) or \
           not os.path.isdir(self.path):
            raise web.HTTPError(404)
        
        self.ctime = os.path.getctime(self.path)

    def __repr__(self):
        return "<Bucket: %s>" % self.name

    @staticmethod
    def all():
        """ list of all buckets """
        buckets = []
        for fn in glob.glob("%s/*.json" % FLAGS.buckets_path):
            try:
                anyjson.deserialize(open(fn).read())
                name = os.path.split(fn)[-1][:-5]
                buckets.append(Bucket(name))
            except:
                pass

        return buckets
    
    @staticmethod
    def create(name, user):
        """ create a new bucket owned by a specific user """
        path = os.path.abspath(os.path.join(
            FLAGS.buckets_path, name))
        if not path.startswith(os.path.abspath(FLAGS.buckets_path)) or \
           os.path.exists(path):
            raise web.HTTPError(403)
        
        os.makedirs(path)
        
        f = open(path+'.json', 'w')
        f.write(anyjson.serialize({'ownerId': user.id}))
        f.close()
        
        
    def to_json(self):
        return {
            "Name": self.name,
            "CreationDate": datetime.datetime.utcfromtimestamp(self.ctime),
        }
    
    @property
    def owner_id(self):
        try:
            return anyjson.deserialize(open(self.path+'.json').read())['ownerId']
        except:
            return None
    
    def is_authorized(self, user):
        try:
            return user.is_admin() or self.owner_id == user.id
        except:
            pass
    
    def list_keys(self, prefix='', marker=None, max_keys=1000, terse=False):
        object_names = []
        for root, dirs, files in os.walk(self.path):
            for file_name in files:
                object_names.append(os.path.join(root, file_name)[len(self.path)+1:])
        object_names.sort()
        contents = []

        start_pos = 0
        if marker:
            start_pos = bisect.bisect_right(object_names, marker, start_pos)
        if prefix:
            start_pos = bisect.bisect_left(object_names, prefix, start_pos)

        truncated = False
        for object_name in object_names[start_pos:]:
            if not object_name.startswith(prefix):
                break
            if len(contents) >= max_keys:
                truncated = True
                break
            object_path = self._object_path(object_name)
            c = {"Key": object_name}
            if not terse:
                info = os.stat(object_path)
                c.update({
                    "LastModified": datetime.datetime.utcfromtimestamp(
                        info.st_mtime),
                    "Size": info.st_size,
                })
            contents.append(c)
            marker = object_name

        return {
            "Name": self.name,
            "Prefix": prefix,
            "Marker": marker,
            "MaxKeys": max_keys,
            "IsTruncated": truncated,
            "Contents": contents,
        }
        
    def _object_path(self, object_name):
        fn = os.path.join(self.path, object_name)
        
        if not fn.startswith(self.path):
            raise web.HTTPError(403)
        
        return fn
    
    def delete(self):
        if len(os.listdir(self.path)) > 0:
            raise web.HTTPError(403)
        os.rmdir(self.path)
        os.remove(self.path+'.json')
    
    def __getitem__(self, key):
        return Object(self, key)
    
    def __setitem__(self, key, value):
        fn = self._object_path(key)
        f = open(fn, 'wb')
        f.write(value)
        f.close()
    
    def __delitem__(self, key):
        Object(self, key).delete()


class Object(object):
    def __init__(self, bucket, key):
        """ wrapper class of an existing key """
        self.bucket = bucket
        self.key = key
        self.path = bucket._object_path(key)
        if not os.path.isfile(self.path):
            raise web.HTTPError(404)

    def __repr__(self):
        return "<Object %s/%s>" % (self.bucket, self.key)

    @property
    def md5(self):
        """ computes the MD5 of the contents of file """
        object_file = open(self.path, "r")
        try:
            hex_md5 = crypto.compute_md5(object_file)
        finally:
            object_file.close()
        return hex_md5

    @property
    def mtime(self):
        """ mtime of file """
        return os.path.getmtime(self.path)
    
    def read(self):
        """ returns the contents of the key """
        return open(self.path, 'rb').read()
    
    def delete(self):
        """ deletes the file """
        os.unlink(self.path)

class Image(object):
    # FIXME: the decrypt stuff is copy/pasted from euca2ools!
    
    def __init__(self, image_id):
        self.image_id = image_id
        self.path = os.path.abspath(os.path.join(FLAGS.images_path, image_id))
        if not self.path.startswith(os.path.abspath(FLAGS.images_path)) or \
           not os.path.isdir(self.path):
            raise web.HTTPError(404)
    
    def delete(self):
        for fn in ['info.json', 'image']:
            try:
                os.unlink(os.path.join(self.path, fn))
            except:
                pass
        try:    
            os.rmdir(self.path)
        except:
            pass
            
    def is_authorized(self, user):
        try:
            return self.json['isPublic'] or info['imageOwnerId'] == user.id
        except:
            pass

    @staticmethod
    def all():
        images = []
        for fn in glob.glob("%s/*/info.json" % FLAGS.images_path):
            try:
                image_id = fn.split('/')[-2]
                images.append(Image(image_id))
            except Exception, e:
                pass
        return images

    @property
    def json(self):
        fn = os.path.join(self.path, 'info.json')
        return anyjson.deserialize(open(fn).read())
    
    @staticmethod
    def create(image_id, image_location, user):
        # FIXME: multiprocess here!

        bucket_name = image_location.split("/")[0]
        manifest_path = image_location[len(bucket_name)+1:]
        bucket = Bucket(bucket_name)
        
        if not bucket.is_authorized(user):
            raise web.HTTPError(403)
        
        tmpdir = tempfile.mkdtemp()
        rawfile = tempfile.NamedTemporaryFile(delete=False)
        encrypted_filename = rawfile.name

        manifest = ElementTree.fromstring(bucket[manifest_path].read())
        encrypted_key = manifest.find("image/ec2_encrypted_key").text
        encrypted_iv = manifest.find("image/ec2_encrypted_iv").text
        # FIXME: grab kernelId and ramdiskId from bundle manifest

        for filename in manifest.find("image").getiterator("filename"):
            rawfile.write(bucket[filename.text].read())
        
        rawfile.close() 
        
        private_key_path = os.path.join(FLAGS.ca_path, "private/cakey.pem")

        image_path = os.path.join(FLAGS.images_path, image_id)
        if not image_path.startswith(FLAGS.images_path) or \
           os.path.exists(image_path):
            raise web.HTTPError(403)
        os.makedirs(image_path)

        decrypted_filename = os.path.join(image_path, 'image.tar.gz')
        Image.decrypt_image(encrypted_filename, encrypted_key, encrypted_iv, private_key_path, decrypted_filename)
        filenames = Image.untarzip_image(image_path, decrypted_filename)
        shutil.move(os.path.join(path, filenames[0]), os.path.join(image_path, 'image'))
        
        info = {
            'imageId': image_id,
            'imageLocation': image_location,
            'imageOwnerId': user.id,
            'imageState': 'available',
            'isPublic': False, # FIXME: grab from bundle manifest
            'architecture': 'x86_64', # FIXME: grab from bundle manifest
            'type' : 'machine',
        }

        object_file = open(os.path.join(image_path, 'info.json'), "w")
        object_file.write(anyjson.serialize(info))
        object_file.close()
            
    @staticmethod
    def decrypt_image(encrypted_filename, encrypted_key, encrypted_iv, private_key_path, decrypted_filename):
        user_priv_key = RSA.load_key(private_key_path)
        key = user_priv_key.private_decrypt(unhexlify(encrypted_key), RSA.pkcs1_padding)
        iv = user_priv_key.private_decrypt(unhexlify(encrypted_iv), RSA.pkcs1_padding)
        k=EVP.Cipher(alg='aes_128_cbc', key=unhexlify(key), iv=unhexlify(iv), op=0)

        # decrypted_filename = encrypted_filename.replace('.enc', '')
        decrypted_file = open(decrypted_filename, "wb")
        encrypted_file = open(encrypted_filename, "rb")
        Image.crypt_file(k, encrypted_file, decrypted_file)
        encrypted_file.close()
        decrypted_file.close()
        return decrypted_filename

    @staticmethod
    def untarzip_image(path, filename):
        untarred_filename = filename.replace('.tar.gz', '') 
        tar_file = tarfile.open(filename, "r|gz")
        tar_file.extractall(path)
        untarred_names = tar_file.getnames()
        tar_file.close()
        return untarred_names 

    @staticmethod
    def crypt_file(cipher, in_file, out_file) :
        while True:
            buf=in_file.read(IMAGE_IO_CHUNK)
            if not buf:
               break
            out_file.write(cipher.update(buf))
        out_file.write(cipher.final())


class S3Application(web.Application):
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

        image = Image.create(image_id=image_id, 
            image_location=image_location, user=self.user)
                
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
