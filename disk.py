from exception import Error
from utils import execute as _ex
import os
import tempfile

import logging

logging.getLogger().setLevel(logging.DEBUG)

def partition(infile, outfile):
    sectors = os.path.getsize(infile) / 512
    start = 63
    end = start + sectors
    # create an empty file
    _ex('dd if=/dev/zero of=%s count=1 seek=%d bs=512' % (outfile, end))

    # make dos partition
    _ex('parted --script %s mklabel msdos' % outfile)

    # make ext2 partion
    _ex('parted --script %s mkpart primary %ds %ds' % (outfile, start, end))

    # copy file into partition
    _ex('dd if=%s of=%s bs=512 seek=%d conv=notrunc,fsync' % (infile, outfile, start))


def inject_key(key, image):
    # try to attach to loopback multiple times
    for i in range(10):
        device = _ex('sudo losetup -f')[0].strip()
        if device:
            out, err = _ex('sudo losetup %s %s ' % (device, image) )
            if not out and not err:
                break
            _ex('sudo losetup -d %s' % device)
    else:
        raise Error('Could not attach image to loopback')
    try:
        # create partition
        out, err = _ex('sudo kpartx -a %s' % device)
        if err:
            raise Error('failed to load partition')
        partition = '/dev/mapper/' + device.split('/')[-1] + 'p1'
        
        out, err = _ex('sudo tune2fs -c 0 -i 0 %s' % partition)
        
        tmpdir = tempfile.mkdtemp()
        try:
            # mount loopback to dir
            out, err = _ex('sudo mount %s %s' % (partition, tmpdir)) 
            if err:
                raise Error('Failed to mount filesystem %s' % err)

            try:
                # inject key file
                _inject_into_fs(key, tmpdir)
            finally:
                # unmount device
                _ex('sudo umount %s' % partition)
        finally:
            # remove temporary directory
            os.rmdir(tmpdir)
            # remove partitions
            _ex('sudo kpartx -d %s' % device)
    finally:
        # remove loopback
        _ex('sudo losetup -d %s' % device)
    
def _inject_into_fs(key, fs):
    sshdir = os.path.join(os.path.join(fs, 'root'), '.ssh')
    _ex('sudo mkdir %s' % sshdir) #error on existing dir doesn't matter
    _ex('sudo chown root %s' % sshdir)
    _ex('sudo chmod 700 %s' % sshdir)
    keyfile = os.path.join(sshdir, 'authorized_keys')
    _ex('sudo bash -c "cat >> %s"' % keyfile, '\n' + key + '\n')

if __name__ == "__main__":
    partition("/home/vishvananda/nasa/images/emi-111111/image",
    "/home/vishvananda/imgtest")
    inject_key("franky", "/home/vishvananda/imgtest")

