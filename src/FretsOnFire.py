# src/FretsOnFire.py
#!/usr/bin/env python3
# -*- coding: iso-8859-1 -*-
#####################################################################
# Frets on Fire
# Copyright (C) 2006 Sami Ky�stil�
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#####################################################################

"""
Main game executable.
"""

import sys
import os
import getopt

# This trickery is needed to get OpenGL 3.x working with py2exe (legacy)
if hasattr(sys, "frozen") and os.name == "nt":
    # Keeping this block for compatibility with the original packaging approach.
    # In a modern Python 3 build (e.g., PyInstaller), this will likely be replaced.
    try:
        import ctypes  # noqa: F401
        from ctypes import util  # noqa: F401
    except Exception:
        pass

    # Only add these paths if they actually exist (avoids crashing on Py3 ports).
    for p in (
        os.path.join("data", "PyOpenGL-3.0.0a5-py2.5.egg"),
        os.path.join("data", "setuptools-0.6c8-py2.5.egg"),
    ):
        if os.path.exists(p):
            sys.path.insert(0, p)

# Register the latin-1 / utf-8 encodings (kept for legacy safety; usually unnecessary in Py3)
import codecs
import encodings.iso8859_1
import encodings.utf_8

codecs.register(lambda encoding: encodings.iso8859_1.getregentry())
codecs.register(lambda encoding: encodings.utf_8.getregentry())
assert codecs.lookup("iso-8859-1")
assert codecs.lookup("utf-8")

from GameEngine import GameEngine
from MainMenu import MainMenu
import Log
import Config
import Version

usage = """%(prog)s [options]
Options:
  --verbose, -v         Verbose messages
  --play, -p [songName] Start playing the given song
""" % {
    "prog": sys.argv[0]
}


def _restart_process():
    """
    Restart the game process, preserving command line args.
    Keeps original behavior, but uses sys.executable on Py3.
    """
    try:
        # Determine whether we're running from an exe or not
        if hasattr(sys, "frozen"):
            if os.name == "nt":
                os.execl("FretsOnFire.exe", "FretsOnFire.exe", *sys.argv[1:])
            elif sys.platform == "darwin":
                # This exit code tells the launcher script to restart the game
                sys.exit(100)
            else:
                os.execl("./FretsOnFire", "./FretsOnFire", *sys.argv[1:])
        else:
            # Restart using the current Python interpreter (works with venv/pyenv/etc.)
            py = sys.executable or "python3"
            os.execl(py, py, os.path.abspath(__file__), *sys.argv[1:])
    except Exception:
        Log.warn("Restart failed.")
        raise


def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:], "vp:", ["verbose", "play="])
    except getopt.GetoptError:
        print(usage)
        return 1

    songName = None
    for opt, arg in opts:
        if opt in ["--verbose", "-v"]:
            Log.quiet = False
        elif opt in ["--play", "-p"]:
            songName = arg

    engine = None

    while True:
        config = Config.load(Version.appName() + ".ini", setAsDefault=True)
        engine = GameEngine(config)
        menu = MainMenu(engine, songName=songName)
        engine.setStartupLayer(menu)

        try:
            import psyco  # type: ignore

            psyco.profile()
        except Exception:
            Log.warn("Unable to enable psyco.")

        try:
            while engine.run():
                pass
        except KeyboardInterrupt:
            pass

        if engine.restartRequested:
            Log.notice("Restarting.")
            _restart_process()
            break
        else:
            break

    if engine is not None:
        engine.quit()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
