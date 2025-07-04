import sqlite3
import threading
from enum import Enum
from typing import Tuple, Optional, Union, cast

from exegol.config.ConstantConfig import ConstantConfig
from exegol.utils.ExeLog import logger
from exegol.utils.MetaSingleton import MetaSingleton


class LocalDatastore(metaclass=MetaSingleton):
    __DB_PATH = ConstantConfig.exegol_config_path / ".datastore"

    class Key(Enum):
        EULA = 0
        SESSION_CERT = 1
        TOKEN = 2
        SESSION = 3

    def __init__(self) -> None:

        sqlite3.threadsafety = 3
        self.__db_lock = threading.Lock()

        self.__is_init = self.__DB_PATH.is_file()
        try:
            self.__db = sqlite3.connect(ConstantConfig.exegol_config_path / ".datastore",
                                        check_same_thread=False,
                                        autocommit=False)  # type: ignore[call-overload]
        except TypeError:
            # autocommit available from python 3.12, before that using isolation_level
            self.__db = sqlite3.connect(ConstantConfig.exegol_config_path / ".datastore",
                                        check_same_thread=False,
                                        isolation_level="IMMEDIATE")

        self.__apply_schema()

    def __apply_schema(self) -> None:
        with self.__db_lock, self.__db:
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
        with self.__db_lock, self.__db:
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
        cursor = self.__db.cursor()
        result = cursor.execute("SELECT * FROM machine").fetchone()
        cursor.close()
        if result is None:
            return None, None
        return result

    def update_mid(self, rid: str, mid: str) -> None:
        with self.__db_lock, self.__db:
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
        with self.__db_lock, self.__db:
            result = self.__db.execute("SELECT value FROM kv WHERE key = ?", (key.value,)).fetchone()
        if result is None:
            return None
        return result[0]

    def set(self, key: Key, value: Optional[Union[str, bytes]]) -> None:
        with self.__db_lock, self.__db:
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
