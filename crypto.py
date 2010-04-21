import M2Crypto
import time
import hashlib
import os
from utils import execute

def generate_keypair(bits=1024):
    # what is the magic 65537?
    
    tmp = execute('mktemp -d')[0].strip()
    if not tmp:
        raise Error('Failed to create temporary directory')
    keyfile = os.path.join(tmp, 'temp')
    execute('ssh-keygen -q -b %d -N "" -f %s' % (bits, keyfile))
    private_key, err = execute('cat %s' % keyfile)
    public_key, err = execute('cat %s.pub' % keyfile)
    execute ('rm -rf %s' % tmp)
    # code below returns public key in pem format
    # key = M2Crypto.RSA.gen_key(bits, 65537, callback=lambda: None)
    # private_key = key.as_pem(cipher=None)
    # bio = M2Crypto.BIO.MemoryBuffer()
    # key.save_pub_key_bio(bio)
    # public_key = bio.read()
    # public_key, err = execute('ssh-keygen -y -f /dev/stdin', private_key)

    return (private_key, public_key)

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
# 
# def decrypt_image_with_system_key(manifest):
#     pk_pem = open('cloud-pk.pem').read()
#   Cipher cipher = Cipher.getInstance( "RSA/ECB/PKCS1Padding" );
#   cipher.init( Cipher.DECRYPT_MODE, pk );
#   cipher.doFinal( Hashes.hexToBytes( encryptedKey ) );
#   cipher.doFinal( Hashes.hexToBytes( encryptedIV ) );
#   String encryptedKey = parser.getValue( "//ec2_encrypted_key" );
#   String encryptedIV = parser.getValue( "//ec2_encrypted_iv" );
#     
# 

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

if __name__ == '__main__':
    private_key, public_key = generate_keypair()
    print private_key + '\n' + public_key   
    
# 
# if __name__ == '__main__':
#     ca, p1, p2 = mkcacert()
# 
# 
# # certGen.addExtension( X509Extensions.BasicConstraints, true, new BasicConstraints( true ) );
# # 
# # Calendar cal = Calendar.getInstance( );
# # certGen.setNotBefore( cal.getTime( ) );
# # cal.add( Calendar.YEAR, 5 );
# # certGen.setNotAfter( cal.getTime( ) );
# # certGen.setSubjectDN( dnName );
# # certGen.setPublicKey( keyPair.getPublic( ) );
# # certGen.setSignatureAlgorithm( this.keySigningAlgorithm );
# # try {
# #   X509Certificate cert = certGen.generate( keyPair.getPrivate( ), PROVIDER );
# #   return cert;
# # } catch ( Exception e ) {
# #   LOG.fatal( e, e );
# #   System.exit( -3 );
# #   return null;
# # }
