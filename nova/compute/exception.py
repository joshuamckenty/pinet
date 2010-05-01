from nova.exception import Error

class NoMoreAddresses(Error):
    pass

class AddressNotAllocated(Error):
    pass

class AddressAlreadyAssociated(Error):
    pass

class AddressNotAssociated(Error):
    pass

class NotValidNetworkSize(Error):
    pass

