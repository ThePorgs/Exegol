from datetime import datetime, timezone
from typing import Optional, cast

from cryptography import x509
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from exegol.exceptions.ExegolExceptions import CancelOperation
from exegol.utils.ExeLog import logger
from exegol.utils.LocalDatastore import LocalDatastore
from exegol.utils.MetaSingleton import MetaSingleton
from exegol.utils.SupabaseUtils import SupabaseUtils


class KeyHandler(metaclass=MetaSingleton):
    __CA = b"""-----BEGIN CERTIFICATE-----
MIICFDCCAXWgAwIBAgIUb1vW91MI9RmY3ckWPu/2zPjiG74wCgYIKoZIzj0EAwIw
IzEhMB8GA1UEAwwYRVhFQ09SUCBST09UIExpY2Vuc2VzIENBMCAXDTI1MDYwMTE1
MjIyMFoYDzIwNzUwNTIwMTUyMjE5WjAjMSEwHwYDVQQDDBhFWEVDT1JQIFJPT1Qg
TGljZW5zZXMgQ0EwgZswEAYHKoZIzj0CAQYFK4EEACMDgYYABAEBp2+vdMrKc4Ty
3SRGJ3/Dxo1q6c90a8Ii37GCAvpSHkQlOra5IZ9YDkw4jhWR/gXVrCiJsYcT1ITt
T7C+Rw/yNQDvEJlWrbQuEFosE7pd0JhVLL1Gb2HlfvFN3SR5+Qre5/unQzMgRhQ/
Ao3ThWVwVeGMOYQwChRDrRFvN0GQh1hWIqNCMEAwDwYDVR0TAQH/BAUwAwEB/zAd
BgNVHQ4EFgQU0zajN86zCCZXjj4jjcdgJ4O3xfAwDgYDVR0PAQH/BAQDAgGGMAoG
CCqGSM49BAMCA4GMADCBiAJCANcis/iuCO8MU337t65f9kpshUCi99Yhw3j/UrbF
2PxDnlB6q1EIpzkh10PQXwm0YW5rg7lMoCGSmm4L7cR3TZDBAkIBhiXNB+bJkDDE
bK214R8IIiJQyepYRvXdWJDflwoWJVhpBIZAHFdKkcw2oJOeRT+eIkmHgxvRHfp7
nvWygzUoHuc=
-----END CERTIFICATE-----"""

    __DEFAULT_PUB_CERT = b"""-----BEGIN CERTIFICATE-----
MIICLTCCAY6gAwIBAgIUc0Ve4qKUxu6aPZ3f5TsRxM/d3UwwCgYIKoZIzj0EAwIw
IzEhMB8GA1UEAwwYRVhFQ09SUCBST09UIExpY2Vuc2VzIENBMB4XDTI1MDYwMTE1
MjIyMFoXDTI4MDUzMTE1MjEzOFowQjEQMA4GA1UECgwHRVhFQ09SUDEQMA4GA1UE
CwwHV1JBUFBFUjEcMBoGA1UEAwwTbGljZW5zZXMuZXhlZ29sLmNvbTBZMBMGByqG
SM49AgEGCCqGSM49AwEHA0IABI+3RkjgH1t1H2gwaRSvoL3oh66/pm4SNcK15/WD
3eG6crZN1+KvATvAJELRiUJeSFqE26AAi7bfstFCYKQ41d+jgYAwfjAMBgNVHRMB
Af8EAjAAMB8GA1UdIwQYMBaAFNM2ozfOswgmV44+I43HYCeDt8XwMB4GA1UdEQQX
MBWCE2xpY2Vuc2VzLmV4ZWdvbC5jb20wHQYDVR0OBBYEFA7OvalfKxJoyZRk5W9c
ULYlyhnwMA4GA1UdDwEB/wQEAwIGwDAKBggqhkjOPQQDAgOBjAAwgYgCQgC4HNlY
ai3+0mXhY0QeYoYFaE2NqyKlpR5DobPw1o1UnQvcOIuHPXGQEIBDUT5Z0175YX74
1+5Jhaz6ILkRLtwxQQJCAPKgauhl0LMsZ9F/QxnnxPi1uJLHLhjf3hj9vjjknaXU
QSipTBpex0X2AoeZ4nLuVLlo8DXYziBk5YFBRKCjQ7xA
-----END CERTIFICATE-----"""

    def __init__(self) -> None:
        # Load current cert from cache
        raw_cert = LocalDatastore().get(LocalDatastore.Key.SESSION_CERT)
        if raw_cert is None:
            # Default cache setup
            raw_cert = self.__DEFAULT_PUB_CERT
            LocalDatastore().set(LocalDatastore.Key.SESSION_CERT, raw_cert)
        if type(raw_cert) is str:
            raw_cert = raw_cert.encode("utf-8")
        assert type(raw_cert) is bytes
        self.__cert: Optional[x509.Certificate] = x509.load_pem_x509_certificate(raw_cert)
        self.__ca_cert = x509.load_pem_x509_certificate(self.__CA)
        if self.__ca_cert.serial_number != 635746069563818933303724671059320780600564128702:
            logger.critical("Wrapper corrupted. Please do not edit your wrapper files. Contact support if needed.")
        if self.__ca_cert.not_valid_after_utc < datetime.now(timezone.utc):
            logger.critical("Your wrapper version is too old. Please update your wrapper.")

        # Cert attributes
        self.__subject: str = ''
        self.__serial_number: str = ''

        if self.__cert is not None and self.__verify_cert(self.__cert):
            self.__update_cert_meta()
        else:
            self.__cert = None

    def __update_cert_meta(self) -> None:
        if self.__cert is None:
            return
        # Cert attributes
        cn = self.__cert.subject.get_attributes_for_oid(x509.NameOID.COMMON_NAME)[0].value
        self.__subject = cn.decode("utf-8") if type(cn) is bytes else cast(str, cn)
        self.__serial_number = "{:x}".format(self.__cert.serial_number).upper()

    def __verify_cert(self, cert: x509.Certificate) -> bool:
        subject = cert.subject.get_attributes_for_oid(x509.NameOID.COMMON_NAME)[0].value
        if type(subject) is bytes:
            subject = subject.decode("utf-8")
        assert type(subject) is str

        builder = x509.verification.PolicyBuilder()
        builder = builder.store(x509.verification.Store([self.__ca_cert]))
        verifier = builder.build_server_verifier(x509.DNSName(subject))
        try:
            verifier.verify(cert, [])
        except x509.verification.VerificationError as e:
            logger.debug(f"Certificate verification failed: {e}")
            return False
        return True

    def getSubject(self) -> str:
        return f"urn:exegol:license_srv:{self.__serial_number}"

    def getKey(self) -> bytes:
        if self.__cert is None:
            raise CancelOperation("Certificate not loaded")
        return self.__cert.public_key().public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo)

    async def refresh_certificate(self, force_refresh: bool = False) -> bool:
        """
        Reload certificate from license server. Return true if the cert have been updated
        :param force_refresh:
        :return:
        """
        cert_changed = False
        # Default refresh only if needed
        if self.__cert is None or force_refresh:
            new_cert_raw = await SupabaseUtils.get_cert()
            new_cert = x509.load_pem_x509_certificate(new_cert_raw)
            if self.__verify_cert(new_cert):
                LocalDatastore().set(LocalDatastore.Key.SESSION_CERT, new_cert_raw)
                cert_changed = self.__cert is None or self.__cert.serial_number != new_cert.serial_number
                self.__cert = new_cert
                self.__update_cert_meta()
            else:
                logger.critical("Your exegol version is no longer compatible. Please update your wrapper or contact support.")
        return cert_changed
