import logging

import M2Crypto
import time
import hashlib
import os
import utils
import tempfile
import shutil
import contrib
import flags

FLAGS = flags.FLAGS

flags.DEFINE_string('ca_file', 'cacert.pem', 'Filename of root CA')
flags.DEFINE_string('keys_path', utils.abspath('../keys'), 'Where we keep our keys')
flags.DEFINE_string('ca_path', utils.abspath('../CA'), 'Where we keep our root CA')

def ca_path(username):
    if username:
        return "%s/INTER/%s/cacert.pem" % (FLAGS.ca_path, username)
    return "%s/cacert.pem" % (FLAGS.ca_path)

def fetch_ca(username=None, chain=True):
    buffer = ""
    with open(ca_path(username),"r") as cafile:
        buffer += cafile.read()
        buffer += "\n"
    if username and not chain:
        return buffer
    with open(ca_path(None),"r") as cafile:
        buffer += cafile.read()
    return buffer

def generate_key_pair(bits=1024):
    # what is the magic 65537?
    
    tmpdir = tempfile.mkdtemp()
    keyfile = os.path.join(tmpdir, 'temp')
    utils.execute('ssh-keygen -q -b %d -N "" -f %s' % (bits, keyfile))
    (out, err) = utils.execute('ssh-keygen -q -l -f %s.pub' % (keyfile))
    fingerprint = out.split(' ')[1]
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

    return (private_key, public_key, fingerprint)

def ssl_pub_to_ssh_pub(ssl_public_key, name='root', suffix='nova'):
    """requires lsh-utils"""
    convert="sed -e'1d' -e'$d' |  pkcs1-conv --public-key-info --base-64 |" \
    + " sexp-conv |  sed -e'1s/(rsa-pkcs1/(rsa-pkcs1-sha1/' |  sexp-conv -s" \
    + " transport | lsh-export-key --openssh"
    (out, err) = utils.execute(convert, ssl_public_key)
    return '%s %s@%s\n' %(out.strip(), name, suffix)

def generate_x509_cert(subject="/C=US/ST=California/L=The Mission/O=CloudFed/OU=NOVA/CN=foo", bits=1024):
    tmpdir = tempfile.mkdtemp()
    keyfile = os.path.abspath(os.path.join(tmpdir, 'temp.key'))
    csrfile = os.path.join(tmpdir, 'temp.csr')
    logging.debug("openssl genrsa -out %s %s" % (keyfile, bits))
    utils.runthis("Generating private key: %s", "openssl genrsa -out %s %s" % (keyfile, bits))
    utils.runthis("Generating CSR: %s", "openssl req -new -key %s -out %s -batch -subj %s" % (keyfile, csrfile, subject))
    private_key = open(keyfile).read()
    csr = open(csrfile).read()
    shutil.rmtree(tmpdir)
    return (private_key, csr)

def sign_csr(csr_text, intermediate=None):  
    if not intermediate:
        return _sign_csr(csr_text, FLAGS.ca_path)
    user_ca = "%s/INTER/%s" % (FLAGS.ca_path, intermediate)
    if not os.path.exists(user_ca):
        start = os.getcwd()
        os.chdir(FLAGS.ca_path)
        utils.runthis("Generating intermediate CA: %s", "sh geninter.sh %s" % (intermediate))
        os.chdir(start)
    return _sign_csr(csr_text, user_ca)
    
def _sign_csr(csr_text, ca_folder):
    #TODO(joshua): Use the intermediate CA
    tmpfolder = tempfile.mkdtemp()
    csrfile = open("%s/inbound.csr" % (tmpfolder), "w")
    csrfile.write(csr_text)
    csrfile.close()
    logging.debug("Flags path: %s" % ca_folder)
    start = os.getcwd()
    # Change working dir to CA
    os.chdir(ca_folder)
    utils.runthis("Signing cert: %s", "openssl ca -batch -out %s/outbound.crt -config ./openssl.cnf -infiles %s/inbound.csr" % (tmpfolder, tmpfolder)) 
    os.chdir(start)
    with open("%s/outbound.crt" % (tmpfolder), "r") as crtfile:
        return crtfile.read()

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

def mkcacert(subject='nova', years=1):
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

