from exception import Error
import subprocess
import os

def _ex(cmd, input=None):
    obj = subprocess.Popen(cmd, shell=True, stdin=subprocess.PIPE,
    stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if input != None:
        result = obj.communicate(input)
    else:
        result = obj.communicate()
    obj.stdin.close()
    return result

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
        _ex('sudo tune2fs -c 0 -i 0 %s >/dev/null 2>&1' % device)
        
        tmp = _ex('sudo mktemp -d')[0].strip()
        if not tmp:
            raise Error('Failed to create temporary directory')
        try:
            # mount loopback to dir
            out, err = _ex('sudo mount %s %s' % (device, tmp)) 
            if err:
                raise Error('Failed to mount filesystem %s' % err)

            try:
                # inject key file
                raw_input('tmp is %s\nPress ENTER to continue' % tmp)
                _inject_into_fs(key, tmp)
            finally:
                # unmount device
                _ex('sudo umount %s' % device)
        finally:
            # remove temporary directory
            _ex('sudo rmdir %s' % tmp)
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
    inject_key("franky", "/var/pinet/images/test.img")

