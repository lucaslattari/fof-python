# src/Log.py
#####################################################################
# -*- coding: iso-8859-1 -*-                                        #
#                                                                   #
# Frets on Fire                                                     #
# Copyright (C) 2006 Sami Ky�stil�                                  #
#####################################################################

import sys
import os

quiet = True
encoding = "iso-8859-1"

if "-v" in sys.argv:
    quiet = False

# Labels with ANSI colors on POSIX (kept as in the original)
if os.name == "posix":
    labels = {
        "warn": "\033[1;33m(W)\033[0m",
        "debug": "\033[1;34m(D)\033[0m",
        "notice": "\033[1;32m(N)\033[0m",
        "error": "\033[1;31m(E)\033[0m",
    }
else:
    labels = {
        "warn": "(W)",
        "debug": "(D)",
        "notice": "(N)",
        "error": "(E)",
    }

# Lazy-initialized log file to avoid circular import with Resource
logFile = None
_log_path = None


def _to_text(msg):
    """
    Convert any object to a safe text string for logging.
    Original Py2 behavior: unicode(msg).encode(encoding, "ignore")
    Here we keep the 'ignore' behavior but return a str.
    """
    try:
        s = str(msg)
    except Exception:
        s = repr(msg)

    return s.encode(encoding, "ignore").decode(encoding, "ignore")


def _ensure_logfile():
    """
    Open the log file on-demand to avoid circular imports.
    """
    global logFile, _log_path
    if logFile is not None:
        return

    try:
        import Resource  # local import to avoid import-time cycle

        path = Resource.getWritableResourcePath()
    except Exception:
        # Fallback: current directory
        path = "."

    try:
        os.makedirs(path, exist_ok=True)
    except Exception:
        pass

    _log_path = os.path.join(path, "fretsonfire.log")
    logFile = open(_log_path, "w", encoding=encoding, errors="ignore", newline="\n")


def log(cls, msg):
    _ensure_logfile()

    text = _to_text(msg)
    line = f"{labels[cls]} {text}"

    if not quiet:
        print(line)

    # logFile is guaranteed by _ensure_logfile()
    logFile.write(line + "\n")
    logFile.flush()


warn = lambda msg: log("warn", msg)
debug = lambda msg: log("debug", msg)
notice = lambda msg: log("notice", msg)
error = lambda msg: log("error", msg)
