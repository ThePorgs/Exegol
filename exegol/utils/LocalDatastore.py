import os
import sqlite3
import sys
import threading
from enum import IntEnum
from typing import Tuple, Optional, Union, cast

from exegol.config.ConstantConfig import ConstantConfig
from exegol.utils.ExeLog import logger
from exegol.utils.FsUtils import get_user_id
from exegol.utils.MetaSingleton import MetaSingleton


class LocalDatastore(metaclass=MetaSingleton):
    __DB_PATH = ConstantConfig.exegol_config_path / ".datastore"

    class Key(IntEnum):
        EULA = 0
        SESSION_CERT = 1
        TOKEN = 2
        SESSION = 3

    def __init__(self) -> None:

        self.__db_lock = threading.Lock()

        self.__is_init = self.__DB_PATH.is_file()
        self.__db = sqlite3.connect(self.__DB_PATH,
                                    check_same_thread=False,
                                    isolation_level=None, # For WAL setup
                                    timeout=5.0)

        # For a new installation, set the owner of the DB to the current user
        if not self.__is_init and sys.platform == "linux" and os.getuid() == 0:
            user_uid, user_gid = get_user_id()
            os.chown(self.__DB_PATH, user_uid, user_gid)

        # Enable Write-Ahead Logging for concurrency (1 Writer, N Readers)
        self.__db.execute("PRAGMA journal_mode=WAL;")

        # Switch back to managed transaction mode
        try:
            # Python 3.12+ (PEP 249 compliant)
            self.__db.autocommit = False  # type: ignore[attr-defined]
        except AttributeError:
            # Python < 3.12 (Legacy mode)
            self.__db.isolation_level = "IMMEDIATE"

        self.__apply_schema()

    def __apply_schema(self) -> None:
        with self.__db_lock:
            try:
                self.__db.execute("CREATE TABLE IF NOT EXISTS machine (rid TEXT NOT NULL, mid TEXT NOT NULL)")
                self.__db.execute("CREATE TABLE IF NOT EXISTS kv (key SMALLINT NOT NULL UNIQUE, value TEXT NOT NULL)")
                self.__db.commit()
            except sqlite3.Error as e:
                self.__db.rollback()
                raise e

    # EULA SECTION

    def is_eula_accepted(self) -> bool:
        return self.get(self.Key.EULA) == "1"

    def update_eula(self, value: bool) -> None:
        self.set(self.Key.EULA, "1" if value else "0")

    # LICENSE SECTION

    def get_license(self) -> Tuple[Optional[str], Optional[str]]:
        token = self.get(LocalDatastore.Key.TOKEN)
        if type(token) is bytes:
            token = token.decode("utf-8")
        session = self.get(LocalDatastore.Key.SESSION)
        if type(session) is bytes:
            session = session.decode("utf-8")
        return cast(Optional[str], session), cast(Optional[str], token)

    def deactivate_license(self) -> None:
        with self.__db_lock:
            logger.debug("DB Deactivating license")
            try:
                self.__db.execute("DELETE FROM kv WHERE key = ?", (self.Key.TOKEN.value,))
                self.__db.execute("DELETE FROM kv WHERE key = ?", (self.Key.SESSION.value,))
                self.__db.commit()
            except sqlite3.Error as e:
                logger.error("DB error during: Deactivating license")
                self.__db.rollback()
                raise e

    # MACHINE SECTION
    def get_machine_id(self) -> Tuple[Optional[str], Optional[str]]:
        result = None
        try:
            cursor = self.__db.execute("SELECT * FROM machine")
            result = cursor.fetchone()
            cursor.close()
        except sqlite3.Error as e:
            logger.error(f"DB error during: Getting machine ID: {e}")
        # Close the implicit read transaction.
        self.__db.rollback()

        if result is None:
            return None, None
        return result

    def update_mid(self, rid: str, mid: str) -> None:
        with self.__db_lock:
            logger.debug("DB Updating DB MID")
            try:
                self.__db.execute("DELETE FROM machine")
                self.__db.execute("INSERT INTO machine (rid, mid) VALUES (?, ?)", (rid, mid,))
                self.__db.commit()
            except sqlite3.Error as e:
                logger.error("DB error during: Updating DB MID")
                self.__db.rollback()
                raise e

    # KV SECTION
    def get(self, key: Key) -> Optional[Union[str, bytes]]:
        result = None
        try:
            # No lock needed for reading in WAL mode
            cursor = self.__db.execute("SELECT value FROM kv WHERE key = ?", (key.value,))
            result = cursor.fetchone()
            cursor.close()
        except sqlite3.Error as e:
            logger.error(f"DB error during: Getting DB KV {key.value}: {e}")
        # Close the implicit read transaction.
        self.__db.rollback()

        if result is None:
            return None
        return result[0]

    def set(self, key: Key, value: Optional[Union[str, bytes]]) -> None:
        with self.__db_lock:
            logger.debug(f"DB Updating KV {key.name}")
            try:
                if value is not None:
                    self.__db.execute("REPLACE INTO kv (key, value) VALUES (?, ?)", (key.value, value,))
                else:
                    self.__db.execute("DELETE FROM kv WHERE key = ?", (key.value,))
                self.__db.commit()
            except sqlite3.Error as e:
                logger.error(f"DB error during: Updating DB KV {key.name}")
                self.__db.rollback()
                raise e
        return None
