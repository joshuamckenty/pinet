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
import anyjson
import xml.etree
from xml.etree import ElementTree
import logging
import flags

FLAGS = flags.FLAGS

logging.getLogger().setLevel(logging.DEBUG)

# Got these from Euca2ools, will need to revisit them
IMAGE_IO_CHUNK = 10 * 1024
IMAGE_SPLIT_CHUNK = IMAGE_IO_CHUNK * 1024;


class S3Application(web.Application):
    """Implementation of an S3-like storage server based on local files.

    If bucket depth is given, we break files up into multiple directories
    to prevent hitting file system limits for number of files in each
    directories. 1 means one level of directories, 2 means 2, etc.
    """
    def __init__(self, buckets_directory, images_directory, bucket_depth=0):
        web.Application.__init__(self, [
            (r"/", RootHandler),
            (r"/_images/", ImageHandler),
            (r"/([^/]+)/(.+)", ObjectHandler),
            (r"/([^/]+)/", BucketHandler),
        ])
        self.directory = os.path.abspath(buckets_directory)
        if not os.path.exists(self.directory):
            os.makedirs(self.directory)
        self.images_directory = os.path.abspath(images_directory)
        if not os.path.exists(self.images_directory):
            os.makedirs(self.images_directory)
        self.bucket_depth = bucket_depth


class BaseRequestHandler(web.RequestHandler):
    SUPPORTED_METHODS = ("PUT", "GET", "DELETE")

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

    def _object_path(self, bucket, object_name):
        if self.application.bucket_depth < 1:
            return os.path.abspath(os.path.join(
                self.application.directory, bucket, object_name))
        hash = hashlib.md5(object_name).hexdigest()
        path = os.path.abspath(os.path.join(
            self.application.directory, bucket))
        for i in range(self.application.bucket_depth):
            path = os.path.join(path, hash[:2 * (i + 1)])
        return os.path.join(path, object_name)


class RootHandler(BaseRequestHandler):
    def get(self):
        names = os.listdir(self.application.directory)
        buckets = []
        for name in names:
            path = os.path.join(self.application.directory, name)
            info = os.stat(path)
            buckets.append({
                "Name": name,
                "CreationDate": datetime.datetime.utcfromtimestamp(
                    info.st_ctime),
            })
        self.render_xml({"ListAllMyBucketsResult": {
            "Buckets": {"Bucket": buckets},
        }})


class BucketHandler(BaseRequestHandler):
    def get(self, bucket_name):
        prefix = self.get_argument("prefix", u"")
        marker = self.get_argument("marker", u"")
        max_keys = int(self.get_argument("max-keys", 50000))
        path = os.path.abspath(os.path.join(self.application.directory,
                                            bucket_name))
        terse = int(self.get_argument("terse", 0))
        if not path.startswith(self.application.directory) or \
           not os.path.isdir(path):
            raise web.HTTPError(404)
        object_names = []
        for root, dirs, files in os.walk(path):
            for file_name in files:
                object_names.append(os.path.join(root, file_name))
        skip = len(path) + 1
        for i in range(self.application.bucket_depth):
            skip += 2 * (i + 1) + 1
        object_names = [n[skip:] for n in object_names]
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
            object_path = self._object_path(bucket_name, object_name)
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
        self.render_xml({"ListBucketResult": {
            "Name": bucket_name,
            "Prefix": prefix,
            "Marker": marker,
            "MaxKeys": max_keys,
            "IsTruncated": truncated,
            "Contents": contents,
        }})

    def put(self, bucket_name):
        path = os.path.abspath(os.path.join(
            self.application.directory, bucket_name))
        if not path.startswith(self.application.directory) or \
           os.path.exists(path):
            raise web.HTTPError(403)
        os.makedirs(path)
        self.finish()

    def delete(self, bucket_name):
        path = os.path.abspath(os.path.join(
            self.application.directory, bucket_name))
        if not path.startswith(self.application.directory) or \
           not os.path.isdir(path):
            raise web.HTTPError(404)
        if len(os.listdir(path)) > 0:
            raise web.HTTPError(403)
        os.rmdir(path)
        self.set_status(204)
        self.finish()


class ImageHandler(BaseRequestHandler):
    def get(self):
        """ returns a json listing of all images 
            that a user has permissions to see """
        
        image_owner_id = self.get_argument('image_owner_id', u'')
    
        images = []
    
        for fn in glob.glob("%s/*/info.json" % self.application.images_directory):
            try:
                info = anyjson.deserialize(open(fn).read())
                if info['isPublic'] or info['imageOwnerId'] == image_owner_id:
                    images.append(info)
            except:
                pass
    
        self.finish(anyjson.serialize(images))

    def decrypt_image(self, encrypted_filename, encrypted_key, encrypted_iv, private_key_path, decrypted_filename):
        user_priv_key = RSA.load_key(private_key_path)
        key = user_priv_key.private_decrypt(unhexlify(encrypted_key), RSA.pkcs1_padding)
        iv = user_priv_key.private_decrypt(unhexlify(encrypted_iv), RSA.pkcs1_padding)
        k=EVP.Cipher(alg='aes_128_cbc', key=unhexlify(key), iv=unhexlify(iv), op=0)
  
        # decrypted_filename = encrypted_filename.replace('.enc', '')
        decrypted_file = open(decrypted_filename, "wb")
        encrypted_file = open(encrypted_filename, "rb")
        self.crypt_file(k, encrypted_file, decrypted_file)
        encrypted_file.close()
        decrypted_file.close()
        return decrypted_filename

    def untarzip_image(self, path, filename):
        untarred_filename = filename.replace('.tar.gz', '') 
        tar_file = tarfile.open(filename, "r|gz")
        tar_file.extractall(path)
        untarred_names = tar_file.getnames()
        tar_file.close()
        return untarred_names 

    def put(self):
        """ create a new registered image """
        image_location = self.get_argument('image_location', u'')
        image_owner_id = self.get_argument('image_owner_id', u'')
        image_id       = self.get_argument('image_id',       u'')
        
        tmpdir = tempfile.mkdtemp()
        rawfile = tempfile.NamedTemporaryFile(delete=False)
        encrypted_filename = rawfile.name
        logging.debug(image_location)
        # TODO(joshua): FUGLY, how do I get the bucket name safely?
        bucketname = image_location.split("/")[0]
        #  ImageLocation           val: ['mybucket/ubuntu-karmic-x86_64.img.manifest.xml']
        tree = ElementTree.ElementTree()
        top = tree.parse(os.path.join(self.application.directory, image_location))
        encrypted_key = top.find("image/ec2_encrypted_key").text
        encrypted_iv = top.find("image/ec2_encrypted_iv").text

        for a in top.find("image").getiterator("filename"):
            filepath = os.path.join(self.application.directory, bucketname, a.text)
            rawfile.write(open(filepath, "rb").read())
        rawfile.close() 
        # FIXME: grab kernelId and ramdiskId from bundle manifest
        
        # FIXME: multiprocess here!
        private_key_path = os.path.join(FLAGS.ca_path, "private/cakey.pem")

        path = os.path.join(self.application.images_directory, image_id)
        if not path.startswith(self.application.images_directory) or \
           os.path.exists(path):
            raise web.HTTPError(403)
        os.makedirs(path)

        decrypted_filename = os.path.join(path, 'image.tar.gz')
        self.decrypt_image(encrypted_filename, encrypted_key, encrypted_iv, private_key_path, decrypted_filename)
        self.untarzip_image(path, decrypted_filename)

        info = {
            'imageId': image_id,
            'imageLocation': image_location,
            'imageOwnerId': image_owner_id,
            'imageState': 'available',
            'isPublic': False, # FIXME: grab from bundle manifest
            'architecture': 'x86_64', # FIXME: grab from bundle manifest
        }

        object_file = open(os.path.join(path, 'info.json'), "w")
        object_file.write(anyjson.serialize(info))
        object_file.close()
        
        self.finish()

    def crypt_file(self, cipher, in_file, out_file) :
        while True:
            buf=in_file.read(IMAGE_IO_CHUNK)
            if not buf:
               break
            out_file.write(cipher.update(buf))
        out_file.write(cipher.final())

        
    def post(self):
        """ update image attributes """
        pass
        

    def delete(self):
        """ delete a registered image """
        image_id = self.get_argument("image_id", u"")
        
        path = os.path.join(self.application.images_directory, image_id)
        if not path.startswith(self.application.images_directory) or \
           not os.path.exists(path):
            raise web.HTTPError(403)
        
        for fn in ['info.json', 'image']:
            os.unlink(os.path.join(path, fn))
            
        os.rmdir(path)

        self.set_status(204)


class ObjectHandler(BaseRequestHandler):
    def get(self, bucket, object_name):
        object_name = urllib.unquote(object_name)
        path = self._object_path(bucket, object_name)
        if not path.startswith(self.application.directory) or \
           not os.path.isfile(path):
            raise web.HTTPError(404)
        info = os.stat(path)
        self.set_header("Content-Type", "application/unknown")
        self.set_header("Last-Modified", datetime.datetime.utcfromtimestamp(
            info.st_mtime))
        object_file = open(path, "r")
        try:
            data = object_file
            self.set_header("Etag", '"' + crypto.compute_md5(data) + '"')
            self.finish(data.read())
        finally:
            object_file.close()

    def put(self, bucket, object_name):
        object_name = urllib.unquote(object_name)
        bucket_dir = os.path.abspath(os.path.join(
            self.application.directory, bucket))
        if not bucket_dir.startswith(self.application.directory) or \
           not os.path.isdir(bucket_dir):
            raise web.HTTPError(404)
        path = self._object_path(bucket, object_name)
        if not path.startswith(bucket_dir) or os.path.isdir(path):
            raise web.HTTPError(403)
        directory = os.path.dirname(path)
        if not os.path.exists(directory):
            os.makedirs(directory)
        object_file = open(path, "w")
        object_file.write(self.request.body)
        object_file.close()
        object_file = open(path, 'r')
        self.set_header("Etag", '"' + crypto.compute_md5(object_file) + '"')
        object_file.close()
        self.finish()

    def delete(self, bucket, object_name):
        object_name = urllib.unquote(object_name)
        path = self._object_path(bucket, object_name)
        if not path.startswith(self.application.directory) or \
           not os.path.isfile(path):
            raise web.HTTPError(404)
        os.unlink(path)
        self.set_status(204)
        self.finish()

