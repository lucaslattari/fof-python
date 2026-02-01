# src/Data.py
#####################################################################
# -*- coding: iso-8859-1 -*-                                        #
#                                                                   #
# Frets on Fire                                                     #
# Copyright (C) 2006 Sami Kytölä                                   #
#####################################################################

from Font import Font
from Texture import Texture
from Svg import SvgDrawing, SvgContext
from Audio import Sound
from Language import _
import random
import Language
import Config

# ------------------------------------------------------------------
# Custom glyph constants (Python 3: str is already Unicode)
# These are control characters used as glyph IDs
# ------------------------------------------------------------------
STAR1 = "\x10"
STAR2 = "\x11"
LEFT = "\x12"
RIGHT = "\x13"
BALL1 = "\x14"
BALL2 = "\x15"


class Data(object):
    """A collection of globally used data resources such as fonts and sound effects."""

    def __init__(self, resource, svg):
        self.resource = resource
        self.svg = svg

        # Load font customization images
        self.loadSvgDrawing(self, "star1", "star1.svg", textureSize=(128, 128))
        self.loadSvgDrawing(self, "star2", "star2.svg", textureSize=(128, 128))
        self.loadSvgDrawing(self, "left", "left.svg", textureSize=(128, 128))
        self.loadSvgDrawing(self, "right", "right.svg", textureSize=(128, 128))
        self.loadSvgDrawing(self, "ball1", "ball1.svg", textureSize=(128, 128))
        self.loadSvgDrawing(self, "ball2", "ball2.svg", textureSize=(128, 128))

        # Load misc images
        self.loadSvgDrawing(self, "loadingImage", "loading.svg", textureSize=(256, 256))

        # Font / language configuration
        asciiOnly = not bool(Language.language)
        rtl = _("__lefttoright__") == "__righttoleft__"
        scale = Config.get("video", "fontscale")
        fontSize = [22, 108]

        if asciiOnly:
            fontFile = resource.fileName("default.ttf")
            bigFontFile = resource.fileName("title.ttf")
        else:
            fontFile = bigFontFile = resource.fileName("international.ttf")

        # Load fonts
        font1 = lambda: Font(
            fontFile,
            fontSize[0],
            scale=scale,
            reversed=rtl,
            systemFont=not asciiOnly,
        )

        font2 = lambda: Font(
            bigFontFile,
            fontSize[1],
            scale=scale,
            reversed=rtl,
            systemFont=not asciiOnly,
        )

        resource.load(self, "font", font1, onLoad=self.customizeFont)
        resource.load(self, "bigFont", font2, onLoad=self.customizeFont)

        # Load sounds
        resource.load(self, "screwUpSounds", self.loadScrewUpSounds)

        self.loadSoundEffect(self, "acceptSound", "in.ogg")
        self.loadSoundEffect(self, "cancelSound", "out.ogg")
        self.loadSoundEffect(self, "selectSound1", "crunch1.ogg")
        self.loadSoundEffect(self, "selectSound2", "crunch2.ogg")
        self.loadSoundEffect(self, "selectSound3", "crunch3.ogg")
        self.loadSoundEffect(self, "startSound", "start.ogg")

    # --------------------------------------------------------------

    def loadSoundEffect(self, target, name, fileName):
        volume = Config.get("audio", "guitarvol")
        path = self.resource.fileName(fileName)
        self.resource.load(
            target,
            name,
            lambda: Sound(path),
            onLoad=lambda s: s.setVolume(volume),
        )

    def loadScrewUpSounds(self):
        return [Sound(self.resource.fileName(f"fiba{i}.ogg")) for i in range(1, 7)]

    # --------------------------------------------------------------

    def loadSvgDrawing(self, target, name, fileName, textureSize=None):
        """
        Load an SVG drawing synchronously.
        """
        path = self.resource.fileName(fileName)
        drawing = self.resource.load(
            target,
            name,
            lambda: SvgDrawing(self.svg, path),
            synch=True,
        )
        if textureSize:
            drawing.convertToTexture(textureSize[0], textureSize[1])
        return drawing

    # --------------------------------------------------------------

    def customizeFont(self, font):
        """Replace predefined glyphs with custom textures."""
        font.setCustomGlyph(STAR1, self.star1.texture)
        font.setCustomGlyph(STAR2, self.star2.texture)
        font.setCustomGlyph(LEFT, self.left.texture)
        font.setCustomGlyph(RIGHT, self.right.texture)
        font.setCustomGlyph(BALL1, self.ball1.texture)
        font.setCustomGlyph(BALL2, self.ball2.texture)

    # --------------------------------------------------------------

    def getSelectSound(self):
        return random.choice(
            [
                self.selectSound1,
                self.selectSound2,
                self.selectSound3,
            ]
        )

    selectSound = property(getSelectSound)

    def getScrewUpSound(self):
        return random.choice(self.screwUpSounds)

    screwUpSound = property(getScrewUpSound)

    # --------------------------------------------------------------

    def essentialResourcesLoaded(self):
        return bool(self.font and self.bigFont)

    def resourcesLoaded(self):
        return None not in self.__dict__.values()
