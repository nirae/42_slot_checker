"""Slot checker exceptions"""

import logging as log
import traceback


def slot_checker_exception(exception, msg=None):
    """Exception handler

    All caught exceptions should call this function.
    Captures traceback unless debug logs are activated.
    Raises generic SlotCheckerException before program terminates.

    Args:
        - exception: exception initially caught
        - msg: optional custom error log
    """

    if msg is not None:
        exc = exception.__name__ if hasattr(exception, __name__) else exception
        log.error(msg)
        log.error("Error originating from %s", exc)
    debug = log.getLogger().getEffectiveLevel() == log.DEBUG
    if not debug:
        log.warning("Traceback may be suppressed. Activate debug logs to see.")
    else:
        traceback.print_exc()
    raise SlotCheckerException(exception)


class SlotCheckerException(Exception):
    """Generic Slot Checker exception"""

    def __init__(self, origin):
        super().__init__()
        self.error_code = 42 if origin == IntraFailedSignin else 1


class IntraFailedSignin(ConnectionRefusedError):
    """Exception raised upon failed login attempt"""


class SlotCheckError(Exception):
    """Exception raised when slots retrieval fails"""
