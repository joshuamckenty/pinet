# Got these from Euca2ools, will need to revisit them

from nova.objectstore import Bucket
from nova.exception import NotFound
from flags import FLAGS

from binascii import unhexlify
import glob
import json
import os
import shutil
import tarfile
import tempfile
from xml.etree import ElementTree
from M2Crypto import EVP, RSA

class Image(object):
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
            return self.metadata['isPublic'] or self.metadata['imageOwnerId'] == user.id
        except:
            return False

    @staticmethod
    def all():
        images = []
        for fn in glob.glob("%s/*/info.json" % FLAGS.images_path):
            try:
                image_id = fn.split('/')[-2]
                images.append(Image(image_id))
            except:
                pass
        return images

    @property
    def metadata(self):
        with open(os.path.join(self.path, 'info.json')) as f:
            return json.load(f)

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
            'isPublic': False, # FIXME: grab public from manifest
            'architecture': 'x86_64', # FIXME: grab architecture from manifest
            'type' : 'machine',
        }

        def write_state(state):
            info['imageState'] = state
            with open(os.path.join(image_path, 'info.json'), "w") as f:
                json.dump(info, f)

        write_state('pending')

        encrypted_file = tempfile.NamedTemporaryFile(delete=False)

        manifest = ElementTree.fromstring(bucket[manifest_path].read())
        encrypted_key = manifest.find("image/ec2_encrypted_key").text
        encrypted_iv = manifest.find("image/ec2_encrypted_iv").text
        # FIXME: grab kernelId and ramdiskId from bundle manifest

        for filename in manifest.find("image").getiterator("filename"):
            shutil.copyfileobj(bucket[filename.text].file, encrypted_file)

        encrypted_file.close()

        write_state('decrypting')

        cloud_private_key = RSA.load_key(os.path.join(FLAGS.ca_path, "private/cakey.pem"))

        decrypted_filename = os.path.join(image_path, 'image.tar.gz')
        Image.decrypt_image(encrypted_file.name, encrypted_key, encrypted_iv, cloud_private_key, decrypted_filename)

        write_state('untarring')

        image_file = Image.untarzip_image(image_path, decrypted_filename)
        shutil.move(os.path.join(image_path, image_file), os.path.join(image_path, 'image'))

        write_state('available')

    @staticmethod
    def decrypt_image(encrypted_filename, encrypted_key, encrypted_iv, cloud_private_key, decrypted_filename):
        key = cloud_private_key.private_decrypt(unhexlify(encrypted_key), RSA.pkcs1_padding)
        iv = cloud_private_key.private_decrypt(unhexlify(encrypted_iv), RSA.pkcs1_padding)
        cipher = EVP.Cipher(alg='aes_128_cbc', key=unhexlify(key), iv=unhexlify(iv), op=0)

        with open(decrypted_filename, 'wb') as out_file:
            with open(encrypted_filename, 'rb') as in_file:
                while True:
                    buf = in_file.read(8192)
                    if not buf:
                        break
                    out_file.write(cipher.update(buf))
                out_file.write(cipher.final())

    @staticmethod
    def untarzip_image(path, filename):
        tar_file = tarfile.open(filename, "r|gz")
        tar_file.extractall(path)
        image_file = tar_file.getnames()[0]
        tar_file.close()
        return image_file
