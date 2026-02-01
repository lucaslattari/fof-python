# src/Language.py
#####################################################################
# -*- coding: iso-8859-1 -*-                                        #
#                                                                   #
# Frets on Fire                                                     #
# Copyright (C) 2006 Sami Ky�stil�                                  #
#                                                                   #
# This program is free software; you can redistribute it and/or     #
# modify it under the terms of the GNU General Public License       #
# as published by the Free Software Foundation; either version 2    #
# of the License, or (at your option) any later version.            #
#                                                                   #
# This program is distributed in the hope that it will be useful,   #
# but WITHOUT ANY WARRANTY; without even the implied warranty of    #
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the     #
# GNU General Public License for more details.                      #
#                                                                   #
# You should have received a copy of the GNU General Public License #
# along with this program; if not, write to the Free Software       #
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,        #
# MA  02110-1301, USA.                                              #
#####################################################################

import glob
import gettext
import os

import Config
import Log
import Version

# Config key (placeholder inicial; depois redefinimos com opções)
Config.define("game", "language", str, "")


def getAvailableLanguages():
    # Ex.: data/translations/Brazilian_portuguese.mo -> "Brazilian portuguese"
    pattern = os.path.join(Version.dataPath(), "translations", "*.mo")
    langs = []
    for path in glob.glob(pattern):
        base = os.path.basename(path)
        # remove extensão
        name = base[:-3] if base.lower().endswith(".mo") else base
        # normaliza "pt_br" -> "Pt br" (mantém a vibe original)
        langs.append(name.capitalize().replace("_", " "))
    return langs


def dummyTranslator(string: str) -> str:
    return string


language = Config.load(Version.appName() + ".ini").get("game", "language")
_ = dummyTranslator

if language:
    try:
        trFile = os.path.join(
            Version.dataPath(),
            "translations",
            f"{language.lower().replace(' ', '_')}.mo",
        )
        with open(trFile, "rb") as f:
            catalog = gettext.GNUTranslations(f)

        def translate(m: str) -> str:
            # Em Python 3, gettext já retorna str (Unicode). Nada de decode.
            return catalog.gettext(m)

        _ = translate
    except Exception as x:
        Log.warn("Unable to select language '%s': %s" % (language, x))
        language = None

# Define a chave de config de novo agora que temos opções reais
langOptions = {"": "English"}
for lang in getAvailableLanguages():
    # Mostra o nome do idioma já traduzido (se houver tradução carregada)
    langOptions[lang] = _(lang)

Config.define("game", "language", str, "", _("Language"), langOptions)
