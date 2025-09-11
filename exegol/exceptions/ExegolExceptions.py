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


class LicenseRevocation(Exception):
    """Custom exception when the license has been revoked"""
    pass


class LicenseToleration(Exception):
    pass


class InteractiveError(Exception):
    """Custom exception when an error occurred. In the interactive mode this error can be retry be the user, in CLI mode this is a critical error"""
    pass
