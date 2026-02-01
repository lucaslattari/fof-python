#####################################################################
# -*- coding: iso-8859-1 -*-                                        #
#                                                                   #
# Frets on Fire                                                     #
# Copyright (C) 2006 Sami Kyöstilä                                  #
#####################################################################

import pygame
from OpenGL.GL import *
from OpenGL.GLU import *
import math
import colorsys

from View import Layer
from Input import KeyListener
from Song import loadSong, createSong, Note, difficulties, DEFAULT_LIBRARY
from Guitar import Guitar, KEYS
from Camera import Camera
from Menu import Menu, Choice
from Language import _

# import MainMenu
import Dialogs
import Player
import Theme
import Log
import shutil
import os
import struct
import wave
import tempfile
from struct import unpack


class Editor(Layer, KeyListener):
    """Song editor layer."""

    def __init__(self, engine, songName=None, libraryName=DEFAULT_LIBRARY):
        self.engine = engine
        self.time = 0.0
        self.guitar = Guitar(self.engine, editorMode=True)
        self.controls = Player.Controls()
        self.camera = Camera()
        self.pos = 0.0
        self.snapPos = 0.0
        self.scrollPos = 0.0
        self.scrollSpeed = 0.0
        self.newNotes = None
        self.newNotePos = 0.0
        self.song = None

        self.engine.loadSvgDrawing(self, "background", "editor.svg")

        self.modified = False
        self.songName = songName
        self.libraryName = libraryName
        self.heldFrets = set()

        mainMenu = [
            (_("Save Song"), self.save),
            (_("Set Song Name"), self.setSongName),
            (_("Set Artist Name"), self.setArtistName),
            (_("Set Beats per Minute"), self.setBpm),
            (_("Estimate Beats per Minute"), self.estimateBpm),
            (_("Set A/V delay"), self.setAVDelay),
            (_("Set Cassette Color"), self.setCassetteColor),
            (_("Set Cassette Label"), self.setCassetteLabel),
            (_("Editing Help"), self.help),
            (_("Quit to Main Menu"), self.quit),
        ]

        self.menu = Menu(self.engine, mainMenu)

    def save(self):
        if not self.modified:
            Dialogs.showMessage(self.engine, _("There are no changes to save."))
            return

        def do_save():
            self.song.save()
            self.modified = False

        self.engine.resource.load(function=do_save)
        Dialogs.showLoadingScreen(
            self.engine, lambda: not self.modified, text=_("Saving...")
        )
        Dialogs.showMessage(self.engine, _("'%s' saved.") % self.song.info.name)

    def help(self):
        Dialogs.showMessage(
            self.engine,
            _("Editing keys: ")
            + _("Arrows - Move cursor, ")
            + _("Space - Play/pause song, ")
            + _("Enter - Make note (hold and move for long notes), ")
            + _("Delete - Delete note, ")
            + _("Page Up/Down - Change difficulty"),
        )

    def setSongName(self):
        name = Dialogs.getText(self.engine, _("Enter Song Name"), self.song.info.name)
        if name:
            self.song.info.name = name
            self.modified = True

    def setArtistName(self):
        name = Dialogs.getText(
            self.engine, _("Enter Artist Name"), self.song.info.artist
        )
        if name:
            self.song.info.artist = name
            self.modified = True

    def setAVDelay(self):
        delay = Dialogs.getText(
            self.engine, _("Enter A/V delay in milliseconds"), str(self.song.info.delay)
        )
        if delay:
            try:
                self.song.info.delay = int(delay)
                self.modified = True
            except ValueError:
                Dialogs.showMessage(self.engine, _("That isn't a number."))

    def setBpm(self):
        bpm = Dialogs.getText(
            self.engine, _("Enter Beats per Minute Value"), str(self.song.bpm)
        )
        if bpm:
            try:
                self.song.setBpm(float(bpm))
                self.modified = True
            except ValueError:
                Dialogs.showMessage(self.engine, _("That isn't a number."))

    def estimateBpm(self):
        bpm = Dialogs.estimateBpm(
            self.engine,
            self.song,
            _(
                "Tap the Space bar to the beat of the song. "
                "Press Enter when done or Escape to cancel."
            ),
        )
        if bpm is not None:
            self.song.setBpm(bpm)
            self.modified = True

    def setCassetteColor(self):
        if not self.song:
            return

        if self.song.info.cassetteColor:
            color = Theme.colorToHex(self.song.info.cassetteColor)
        else:
            color = ""

        color = Dialogs.getText(
            self.engine,
            _("Enter cassette color in HTML (#RRGGBB) format."),
            color,
        )

        if color:
            try:
                self.song.info.setCassetteColor(Theme.hexToColor(color))
                self.modified = True
            except ValueError:
                Dialogs.showMessage(self.engine, _("That isn't a color."))

    def setCassetteLabel(self):
        if not self.songName:
            return

        label = Dialogs.chooseFile(
            self.engine,
            masks=["*.png"],
            prompt=_("Choose a 256x128 PNG format label image."),
        )

        if label:
            songPath = self.engine.resource.fileName(
                "songs",
                self.songName,
                writable=True,
            )
            shutil.copyfile(label, os.path.join(songPath, "label.png"))
            self.modified = True

    def quit(self):
        self.engine.view.popLayer(self)
        self.engine.view.popLayer(self.menu)


class Importer(Layer):
    """
    Song importer.

    This importer needs two OGG tracks for the new song; one is the background track
    and the other is the guitar track. The importer will create a blank note and info files
    and copy the tracks under the data directory.
    """

    def __init__(self, engine):
        self.engine = engine
        self.wizardStarted = False
        self.song = None
        self.songName = None

    def hidden(self):
        if self.songName:
            self.engine.view.pushLayer(Editor(self.engine, self.songName))
        else:
            from MainMenu import MainMenu

            self.engine.view.pushLayer(MainMenu.MainMenu(self.engine))

    def run(self, ticks):
        if self.wizardStarted:
            return
        self.wizardStarted = True

        name = ""
        while True:
            masks = ["*.ogg"]
            name = Dialogs.getText(
                self.engine, prompt=_("Enter a name for the song."), text=name
            )

            if not name:
                self.engine.view.popLayer(self)
                return

            path = os.path.abspath(self.engine.resource.fileName("songs", name))
            if os.path.isdir(path):
                Dialogs.showMessage(self.engine, _("That song already exists."))
            else:
                break

        guitarTrack = Dialogs.chooseFile(
            self.engine,
            masks=masks,
            prompt=_("Choose the Instrument Track (OGG format)."),
        )

        if not guitarTrack:
            self.engine.view.popLayer(self)
            return

        backgroundTrack = Dialogs.chooseFile(
            self.engine,
            masks=masks,
            prompt=_(
                "Choose the Background Track (OGG format) or press Escape to skip."
            ),
        )

        loader = self.engine.resource.load(
            self,
            "song",
            lambda: createSong(self.engine, name, guitarTrack, backgroundTrack),
        )

        Dialogs.showLoadingScreen(
            self.engine, lambda: self.song or loader.exception, text=_("Importing...")
        )

        if not loader.exception:
            self.songName = name

        self.engine.view.popLayer(self)


class ArkFile(object):
    """
    An interface to the ARK file format of Guitar Hero.
    """

    def __init__(self, indexFileName, dataFileName):
        self.dataFileName = dataFileName

        f = open(indexFileName, "rb")
        magic, version1, version2, arkSize, length = unpack("IIIII", f.read(5 * 4))

        Log.debug(
            "Reading HDR file v%d.%d. Main archive is %d bytes."
            % (version1, version2, arkSize)
        )

        fileNameData = f.read(length)
        (fileNameCount,) = unpack("I", f.read(4))
        fileNameOffsets = [unpack("I", f.read(4))[0] for _ in range(fileNameCount)]

        names = []
        for offset in fileNameOffsets:
            end = fileNameData[offset:].find(b"\x00")
            name = fileNameData[offset : offset + end].decode("ascii", "ignore")
            names.append(name)

        (fileCount,) = unpack("I", f.read(4))

        self.files = {}
        for _ in range(fileCount):
            offset, fileIndex, dirIndex, length, _ = unpack("IIIII", f.read(5 * 4))
            fullName = "%s/%s" % (names[dirIndex], names[fileIndex])
            self.files[fullName] = (offset, length)
            Log.debug(
                "File: %s at offset %d, length %d bytes." % (fullName, offset, length)
            )

        Log.debug("Archive contains %d files." % len(self.files))
        f.close()

    def openFile(self, name, mode="rb"):
        offset, _ = self.files[name]
        f = open(self.dataFileName, mode)
        f.seek(offset)
        return f

    def fileLength(self, name):
        _, length = self.files[name]
        return length

    def extractFile(self, name, outputFile):
        f = self.openFile(name)
        length = self.fileLength(name)

        if isinstance(outputFile, str):
            out = open(outputFile, "wb")
        else:
            out = outputFile

        while length > 0:
            data = f.read(4096)
            data = data[: min(length, len(data))]
            length -= len(data)
            out.write(data)

        f.close()
        if isinstance(outputFile, str):
            out.close()


class GHImporter(Layer):
    """
    Guitar Hero(tm) song importer.
    """

    def __init__(self, engine):
        self.engine = engine
        self.wizardStarted = False
        self.done = False
        self.songs = None
        self.statusText = ""
        self.stageInfoText = ""
        self.stageProgress = 0.0

    def hidden(self):
        self.engine.boostBackgroundThreads(False)
        from MainMenu import MainMenu

        self.engine.view.pushLayer(MainMenu.MainMenu(self.engine))

    # --- PORT NOTE ---
    # decodeVgsStreams / decodeVgsFile / joinPcmFiles / importSongs
    # mantêm lógica original; apenas ajustes de bytes/str e print removido

    # ⚠️ trecho crítico corrigido:
    # assert magic == b"VgS!"

    # dentro de decodeVgsFile:
    # magic, version = unpack("4si", header[:8])
    # assert magic == b"VgS!"
