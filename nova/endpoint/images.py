import boto
import boto.s3
import random
import anyjson
import urllib
import flags
from nova.utils import generate_uid

FLAGS = flags.FLAGS

def register(user, image_location):
    image_id = generate_uid('ami')
    
    conn(user).make_request(
            method='PUT',
            bucket='_images',
            query_args=qs({'image_location': image_location,
                           'image_id': image_id}))
    
    return image_id

def list(user, only_images=[]):
    # FIXME: send along the list of only_images to check for
    response = conn(user).make_request(
            method='GET', 
            bucket='_images')

    return anyjson.deserialize(response.read())

def deregister(user, image_id):
    conn(user).make_request(
            method='DELETE',
            bucket='_images',
            query_args=qs({'image_id': image_id}))

def conn(user):
    return boto.s3.connection.S3Connection (
        aws_access_key_id=user.access,
        aws_secret_access_key=user.secret,
        is_secure=False,
        calling_format=boto.s3.connection.OrdinaryCallingFormat(),
        port=FLAGS.s3_port,
        host=FLAGS.s3_host)

def qs(params):
    pairs = []
    for key in params.keys():
        pairs.append(key + '=' + urllib.quote(params[key]))
    return '&'.join(pairs)
