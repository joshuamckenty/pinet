# This script is invoked by Pinet for converting partitions to disks.
# If given a partition, it will overwrite it with a disk containing that
# partition and, optionally, with new swap and ephemeral partitions, too.

import math
import os
import subprocess

def convert(root_partition_path, dest_image_path, ephemeral=0, swap=0):
    root_size = os.path.getsize(root_partition_path)
    size_mb = int(math.ceil(root_size / (1024000.0))) + ephemeral + swap

    # Create the disk image
    # FIXME: does skipping speed things up since it doesn't overwrite whatever is on the disk except for the last byte?
    subprocess.call(['dd', 'if=/dev/zero', 'of='+dest_image_path, 'bs=1M', 'seek='+str(size_mb-1), 'count=1'])
    subprocess.call(['parted', '--script', dest_image_path, 'mklabel msdos'])

    # create the root partition
    first_sector = 63 # DOS starting sector
    last_sector = first_sector + (root_size / 512) # FIXME: shouldn't it be the ceil of that?
    subprocess.call(['parted', '--script', dest_image_path, 'mkpart primary ext2 %ds %ds' % (first_sector, last_sector)])

    # copy the partition
    subprocess.call(['dd', 'if='+root_partition_path, 'of='+dest_image_path, 'bs=512', 'seek=63', 'conv=notrunc,fsync'])

    # FIXME: implement ephemeral & swap

