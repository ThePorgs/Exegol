# Exceptions specific to the successful operation of exegol
class ObjectNotFound(Exception):
    """Custom exception when a specific container do not exist"""
    pass


class ProtocolNotSupported(Exception):
    """Custom exception when a specific network protocol is not supported"""
    pass


class CancelOperation(Exception):
    """Custom exception when an error occurred and the operation must be canceled ou skipped"""
    pass
