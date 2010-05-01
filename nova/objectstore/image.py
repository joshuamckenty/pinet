# Got these from Euca2ools, will need to revisit them
# from nova import objectstore

from nova.objectstore import Bucket
from nova.exception import NotFound, NotAuthorized

import glob
import os
import tarfile
from xml.etree import ElementTree
import tempfile
from M2Crypto import EVP, RSA
from binascii import unhexlify

class Image(object):
    IMAGE_IO_CHUNK = 10 * 1024
    
    def __init__(self, image_id):
        self.image_id = image_id
        self.path = os.path.abspath(os.path.join(FLAGS.images_path, image_id))
        if not self.path.startswith(os.path.abspath(FLAGS.images_path)) or \
           not os.path.isdir(self.path):
            raise NotFound
    
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
            return self.json['isPublic'] or self.json['imageOwnerId'] == user.id
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
        image_path = os.path.join(FLAGS.images_path, image_id)
        os.makedirs(image_path)

        bucket_name = image_location.split("/")[0]
        manifest_path = image_location[len(bucket_name)+1:]
        bucket = Bucket(bucket_name)

        info = {
            'imageId': image_id,
            'imageLocation': image_location,
            'imageOwnerId': user.id,
            'imageState': 'pending',
            'isPublic': False, # FIXME: grab from bundle manifest
            'architecture': 'x86_64', # FIXME: grab from bundle manifest
            'type' : 'machine',
        }

        with open(os.path.join(image_path, 'info.json'), "w") as f:
            f.write(anyjson.serialize(info))

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
        
        info['imageState'] = 'decrypting'
        with open(os.path.join(image_path, 'info.json'), "w") as f:
            f.write(anyjson.serialize(info))
        
        private_key_path = os.path.join(FLAGS.ca_path, "private/cakey.pem")
        decrypted_filename = os.path.join(image_path, 'image.tar.gz')
        Image.decrypt_image(encrypted_filename, encrypted_key, encrypted_iv, private_key_path, decrypted_filename)

        info['imageState'] = 'untarring'
        with open(os.path.join(image_path, 'info.json'), "w") as f:
            f.write(anyjson.serialize(info))

        filenames = Image.untarzip_image(image_path, decrypted_filename)
        shutil.move(os.path.join(image_path, filenames[0]), os.path.join(image_path, 'image'))
        
        info['imageState'] = 'available'
        with open(os.path.join(image_path, 'info.json'), "w") as f:
            f.write(anyjson.serialize(info))
            
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
            buf=in_file.read(Image.IMAGE_IO_CHUNK)
            if not buf:
               break
            out_file.write(cipher.update(buf))
        out_file.write(cipher.final())
