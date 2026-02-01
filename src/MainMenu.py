# src/MainMenu.py
#####################################################################
# -*- coding: iso-8859-1 -*-                                        #
#                                                                   #
# Frets on Fire                                                     #
# Copyright (C) 2006 Sami Ky�stil�                                  #
#####################################################################

from OpenGL.GL import *  # noqa: F401,F403  (mantido como no original)
import math
import socket

from View import BackgroundLayer
from Menu import Menu
from Editor import Editor, Importer, GHImporter
from Credits import Credits
from Lobby import Lobby
from Svg import SvgDrawing  # noqa: F401  (muitos layers dependem disso; mantido)
from Language import _
import Dialogs
import Config
import Audio
import Settings


class MainMenu(BackgroundLayer):
    def __init__(self, engine, songName=None):
        self.engine = engine
        self.time = 0.0
        self.nextLayer = None
        self.visibility = 0.0
        self.songName = songName

        # SVG assets
        self.engine.loadSvgDrawing(self, "background", "keyboard.svg")
        self.engine.loadSvgDrawing(self, "guy", "pose.svg")
        self.engine.loadSvgDrawing(self, "logo", "logo.svg")

        # Menu music
        self.song = Audio.Sound(self.engine.resource.fileName("menu.ogg"))
        self.song.setVolume(self.engine.config.get("audio", "songvol"))
        self.song.play(-1)

        # Kept for future use / parity with original structure
        self.newMultiplayerMenu = [
            (_("Host Multiplayer Game"), self.hostMultiplayerGame),
            (_("Join Multiplayer Game"), self.joinMultiplayerGame),
        ]

        editorMenu = Menu(
            self.engine,
            [
                (_("Edit Existing Song"), self.startEditor),
                (_("Import New Song"), self.startImporter),
                (_("Import Guitar Hero(tm) Songs"), self.startGHImporter),
            ],
        )

        settingsMenu = Settings.SettingsMenu(self.engine)

        mainMenu = [
            (_("Play Game"), self.newSinglePlayerGame),
            (_("Tutorial"), self.showTutorial),
            (_("Song Editor"), editorMenu),
            (_("Settings >"), settingsMenu),
            (_("Credits"), self.showCredits),
            (_("Quit"), self.quit),
        ]

        self.menu = Menu(
            self.engine,
            mainMenu,
            onClose=lambda: self.engine.view.popLayer(self),
        )

    def shown(self):
        self.engine.view.pushLayer(self.menu)
        self.engine.stopServer()

        if self.songName:
            self.newSinglePlayerGame(self.songName)

    def hidden(self):
        self.engine.view.popLayer(self.menu)

        if self.song:
            self.song.fadeout(1000)

        if self.nextLayer:
            self.engine.view.pushLayer(self.nextLayer())
            self.nextLayer = None
        else:
            self.engine.quit()

    def quit(self):
        self.engine.view.popLayer(self.menu)

    # ------------------------------------------------------------
    # Error harness (Py3 port)
    # ------------------------------------------------------------
    @staticmethod
    def catchErrors(function):
        def harness(self, *args, **kwargs):
            try:
                try:
                    function(self, *args, **kwargs)
                except Exception:
                    import traceback

                    traceback.print_exc()
                    raise
            except OSError as e:
                # In Py3, socket.error is an alias/subclass of OSError.
                # Keep behavior: show human message.
                Dialogs.showMessage(self.engine, str(e))
            except KeyboardInterrupt:
                pass
            except Exception as e:
                if e:
                    Dialogs.showMessage(self.engine, str(e))

        return harness

    def launchLayer(self, layerFunc):
        if not self.nextLayer:
            self.nextLayer = layerFunc
            self.engine.view.popAllLayers()

    def showTutorial(self):
        if self.engine.isServerRunning():
            return
        self.engine.startServer()
        self.engine.resource.load(
            self,
            "session",
            lambda: self.engine.connect("127.0.0.1"),
            synch=True,
        )

        if Dialogs.showLoadingScreen(
            self.engine, lambda: self.session and self.session.isConnected
        ):
            self.launchLayer(
                lambda: Lobby(
                    self.engine, self.session, singlePlayer=True, songName="tutorial"
                )
            )

    showTutorial = catchErrors(showTutorial)

    def newSinglePlayerGame(self, songName=None):
        if self.engine.isServerRunning():
            return
        self.engine.startServer()
        self.engine.resource.load(
            self,
            "session",
            lambda: self.engine.connect("127.0.0.1"),
            synch=True,
        )

        if Dialogs.showLoadingScreen(
            self.engine, lambda: self.session and self.session.isConnected
        ):
            self.launchLayer(
                lambda: Lobby(
                    self.engine, self.session, singlePlayer=True, songName=songName
                )
            )

    newSinglePlayerGame = catchErrors(newSinglePlayerGame)

    def hostMultiplayerGame(self):
        self.engine.startServer()
        self.engine.resource.load(
            self, "session", lambda: self.engine.connect("127.0.0.1")
        )

        if Dialogs.showLoadingScreen(
            self.engine, lambda: self.session and self.session.isConnected
        ):
            self.launchLayer(lambda: Lobby(self.engine, self.session))

    hostMultiplayerGame = catchErrors(hostMultiplayerGame)

    def joinMultiplayerGame(self, address=None):
        if not address:
            address = Dialogs.getText(
                self.engine, _("Enter the server address:"), "127.0.0.1"
            )

        if not address:
            return

        self.engine.resource.load(self, "session", lambda: self.engine.connect(address))

        if Dialogs.showLoadingScreen(
            self.engine,
            lambda: self.session and self.session.isConnected,
            text=_("Connecting..."),
        ):
            self.launchLayer(lambda: Lobby(self.engine, self.session))

    joinMultiplayerGame = catchErrors(joinMultiplayerGame)

    def startEditor(self):
        self.launchLayer(lambda: Editor(self.engine))

    startEditor = catchErrors(startEditor)

    def startImporter(self):
        self.launchLayer(lambda: Importer(self.engine))

    startImporter = catchErrors(startImporter)

    def startGHImporter(self):
        self.launchLayer(lambda: GHImporter(self.engine))

    startGHImporter = catchErrors(startGHImporter)

    def showCredits(self):
        self.launchLayer(lambda: Credits(self.engine))

    showCredits = catchErrors(showCredits)

    def run(self, ticks):
        self.time += ticks / 50.0

    def render(self, visibility, topMost):
        self.visibility = visibility
        v = 1.0 - ((1 - visibility) ** 2)

        t = self.time / 100.0
        w, h = self.engine.view.geometry[2:4]
        r = 0.5

        self.background.transform.reset()
        self.background.transform.translate(
            (1 - v) * 2 * w + w / 2 + math.cos(t / 2) * w / 2 * r,
            h / 2 + math.sin(t) * h / 2 * r,
        )
        self.background.transform.rotate(-t)
        self.background.transform.scale(math.sin(t / 8) + 2, math.sin(t / 8) + 2)
        self.background.draw()

        self.logo.transform.reset()
        self.logo.transform.translate(0.5 * w, 0.8 * h + (1 - v) * h * 2 * 0)
        f1 = math.sin(t * 16) * 0.025
        f2 = math.cos(t * 17) * 0.025
        self.logo.transform.scale(1 + f1 + (1 - v) ** 3, -1 + f2 + (1 - v) ** 3)
        self.logo.draw()

        self.guy.transform.reset()
        self.guy.transform.translate(0.75 * w + (1 - v) * 2 * w, 0.35 * h)
        self.guy.transform.scale(-0.9, 0.9)
        self.guy.transform.rotate(math.pi)
        self.guy.draw()
