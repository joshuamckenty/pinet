import M2Crypto
import time
import hashlib
import os
import utils
from utils import execute
from utils import runthis
import tempfile
import shutil
import logging
import contrib
import flags
import utils

FLAGS = flags.FLAGS

flags.DEFINE_string('ca_file', 'cacert.pem', 'Filename of root CA')
flags.DEFINE_string('keys_path', utils.abspath('keys'), 'Where we keep our keys')
flags.DEFINE_string('ca_path', utils.abspath('CA'), 'Where we keep our root CA')

def generate_keypair(bits=1024):
    # what is the magic 65537?
    
    tmpdir = tempfile.mkdtemp()
    keyfile = os.path.join(tmpdir, 'temp')
    execute('ssh-keygen -q -b %d -N "" -f %s' % (bits, keyfile))
    private_key = open(keyfile).read()
    public_key = open(keyfile + '.pub').read()
    shutil.rmtree(tmpdir)
    # code below returns public key in pem format
    # key = M2Crypto.RSA.gen_key(bits, 65537, callback=lambda: None)
    # private_key = key.as_pem(cipher=None)
    # bio = M2Crypto.BIO.MemoryBuffer()
    # key.save_pub_key_bio(bio)
    # public_key = bio.read()
    # public_key, err = execute('ssh-keygen -y -f /dev/stdin', private_key)

    return (private_key, public_key)


def generate_x509_cert(subject="/C=US/ST=California/L=The Mission/O=CloudFed/OU=PINET/CN=foo", bits=1024):
    tmpdir = tempfile.mkdtemp()
    keyfile = os.path.abspath(os.path.join(tmpdir, 'temp.key'))
    csrfile = os.path.join(tmpdir, 'temp.csr')
    logging.debug("openssl genrsa -out %s %s" % (keyfile, bits))
    runthis("Generating private key: %s", "openssl genrsa -out %s %s" % (keyfile, bits))
    runthis("Generating CSR: %s", "openssl req -new -key %s -out %s -batch -subj %s" % (keyfile, csrfile, subject))
    private_key = open(keyfile).read()
    csr = open(csrfile).read()
    shutil.rmtree(tmpdir)
    return (private_key, csr)

def sign_csr(csr_text):
    tmpfolder = tempfile.mkdtemp()
    csrfile = open("%s/inbound.csr" % (tmpfolder), "w")
    csrfile.write(csr_text)
    csrfile.close()
    start = os.getcwd()
    # Change working dir to CA
    os.chdir(FLAGS.ca_path)
    runthis("Signing cert: %s", "openssl ca -batch -out %s/outbound.crt -config ./openssl.cnf -infiles %s/inbound.csr" % (tmpfolder, tmpfolder)) 
    crtfile = open("%s/outbound.crt" % (tmpfolder), "r")
    crttext = crtfile.read()
    crtfile.close()
    os.chdir(start)
    return crttext

def compute_md5(fp):
    """
    # FIXME: from boto
    @type fp: file
    @param fp: File pointer to the file to MD5 hash.  The file pointer will be
               reset to the beginning of the file before the method returns.

    @rtype: tuple
    @return: the hex digest version of the MD5 hash
    """
    m = hashlib.md5()
    fp.seek(0)
    s = fp.read(8192)
    while s:
        m.update(s)
        s = fp.read(8192)
    hex_md5 = m.hexdigest()
    # size = fp.tell()
    fp.seek(0)
    return hex_md5

def mkreq(bits, subject="foo", ca=0):
    pk = M2Crypto.EVP.PKey()
    req = M2Crypto.X509.Request()
    rsa = M2Crypto.RSA.gen_key(bits, 65537, callback=lambda: None)
    pk.assign_rsa(rsa)
    rsa = None # should not be freed here
    req.set_pubkey(pk)
    req.set_subject(subject)
    req.sign(pk,'sha512')
    assert req.verify(pk)
    pk2 = req.get_pubkey()
    assert req.verify(pk2)
    return req, pk

def mkcacert(subject='pinet', years=1):
    req, pk = mkreq(2048, subject, ca=1)
    pkey = req.get_pubkey()
    sub = req.get_subject()
    cert = M2Crypto.X509.X509()
    cert.set_serial_number(1)
    cert.set_version(2)
    cert.set_subject(sub) # FIXME subject is not set in mkreq yet
    t = long(time.time()) + time.timezone
    now = M2Crypto.ASN1.ASN1_UTCTIME()
    now.set_time(t)
    nowPlusYear = M2Crypto.ASN1.ASN1_UTCTIME()
    nowPlusYear.set_time(t + (years * 60 * 60 * 24 * 365))
    cert.set_not_before(now)
    cert.set_not_after(nowPlusYear)
    issuer = M2Crypto.X509.X509_Name()
    issuer.C = "US"
    issuer.CN = subject
    cert.set_issuer(issuer)
    cert.set_pubkey(pkey) 
    ext = M2Crypto.X509.new_extension('basicConstraints', 'CA:TRUE')
    cert.add_ext(ext)
    cert.sign(pk, 'sha512')
    
    # print 'cert', dir(cert)
    print cert.as_pem()
    print pk.get_rsa().as_pem()
    
    return cert, pk, pkey

