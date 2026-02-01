# src/Version.py
#####################################################################
# -*- coding: iso-8859-1 -*-                                        #
#                                                                   #
# Frets on Fire                                                     #
# Copyright (C) 2006 Sami Ky�stil�                                  #
#####################################################################

import sys
import os

VERSION = "1.3"


def appName():
    return "fretsonfire"


def revision():
    """
    Legacy SVN revision marker.
    Kept for compatibility with the original versioning scheme.
    """
    try:
        return int("$LastChangedRevision: 110 $".split(" ")[1])
    except Exception:
        # Fallback in case the format ever changes
        return 0


def version():
    return "%s.%d" % (VERSION, revision())


import os
import sys


def dataPath():
    """
    Determine where the game data directory is located.

    Comportamento:
    - Preserva lógica legacy para builds congeladas (py2exe / frozen)
    - Em modo script (Python 3 moderno), resolve o caminho absoluto
      com base na localização real do código-fonte (Version.py)
    """

    # Caso executável congelado (comportamento legacy)
    if hasattr(sys, "frozen"):
        if os.name == "posix":
            data_path = os.path.join(os.path.dirname(sys.argv[0]), "../lib/fretsonfire")
            if not os.path.isdir(data_path):
                data_path = "data"
        else:
            data_path = "data"

        return os.path.abspath(data_path)

    # Caso normal: execução via python src/FretsOnFire.py
    here = os.path.abspath(os.path.dirname(__file__))  # src/
    project_root = os.path.abspath(os.path.join(here, ".."))
    data_path = os.path.join(project_root, "data")

    return data_path
