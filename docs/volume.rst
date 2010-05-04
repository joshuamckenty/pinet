Volume Documentation
====================
                           
Nova uses ata-over-ethernet (AoE) to export storage volumes from multiple storage nodes. These AoE exports are attached (using libvirt) directly to running instances.

Nova volumes are exported over the primary system VLAN (usually VLAN 1), and not over individual VLANs.

AoE exports are numbered according to a "shelf and blade" syntax. In order to avoid collisions, we currently perform an AoE-discover of existing exports, and then grab the next unused number. (This obviously has race condition problems, and should be replaced by allocating a shelf-id to each storage node.)

The underlying volumes are LVM logical volumes, created on demand within a single large volume group. 



Subpackages
-----------

.. toctree::

    volume.tests

The :mod:`storage` Module
-------------------------

.. automodule:: nova.volume.storage
    :members:
    :undoc-members:
    :show-inheritance:

The :mod:`storage_worker` Module
--------------------------------

.. automodule:: nova.volume.storage_worker
    :members:
    :undoc-members:
    :show-inheritance:

