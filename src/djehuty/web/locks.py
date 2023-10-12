"""This module provides thread- and process locks for sensitive procedures."""

from enum import Enum
from threading import Lock
try:
    import uwsgi
except ModuleNotFoundError:
    pass

class LockTypes(Enum):
    """Enumeration of lock types."""
    FILE_LIST     = 1
    PRIVATE_LINKS = 2
    AUTHORS       = 3
    SUBMIT_DATASET = 4
    DATASET_LIST  = 5

class Locks:
    """This class implements multiple locks"""

    ## Only ever allow one instance of this class to exist,
    ## so that we prevent re-initializing locks.
    _instance = None
    def __new__ (cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__ (self):
        self.locks = {
            LockTypes.FILE_LIST: Lock(),
            LockTypes.PRIVATE_LINKS: Lock(),
            LockTypes.AUTHORS: Lock(),
            LockTypes.SUBMIT_DATASET: Lock(),
            LockTypes.DATASET_LIST: Lock()
        }

        self.using_uwsgi = False

    def lock (self, lock_type):
        """Lock critical section LOCK_TYPE."""

        if self.using_uwsgi:
            uwsgi.lock(lock_type.value)
        else:
            lock = self.locks.get(lock_type)
            lock.acquire(blocking=True, timeout=30)

    def unlock (self, lock_type):
        """Unlock critical section LOCK_TYPE."""
        if self.using_uwsgi:
            uwsgi.unlock(lock_type.value)
        else:
            lock = self.locks.get(lock_type)
            lock.release()
