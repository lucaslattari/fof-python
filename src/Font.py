import pygame
import numpy
from OpenGL.GL import *
import sys

from Texture import Texture, TextureAtlas, TextureAtlasFullException


class Font:
    """A texture-mapped font."""

    def __init__(
        self,
        fileName,
        size,
        bold=False,
        italic=False,
        underline=False,
        outline=True,
        scale=1.0,
        reversed=False,
        systemFont=False,
    ):
        pygame.font.init()
        self.size = size
        self.scale = scale

        self.glyphCache = {}
        self.glyphSizeCache = {}

        self.outline = outline
        self.reversed = reversed

        # ✅ Corrigido: estruturas que faltavam
        self.glyphTextures = []
        self.atlases = []

        self.stringCache = {}
        self.stringCacheLimit = 256

        self.font = None
        if systemFont and sys.platform != "win32":
            try:
                self.font = pygame.font.SysFont(None, size)
            except Exception:
                pass

        if not self.font:
            self.font = pygame.font.Font(fileName, size)

        self.font.set_bold(bold)
        self.font.set_italic(italic)
        self.font.set_underline(underline)

    def getStringSize(self, s, scale=0.002):
        w = 0
        h = 0
        scale *= self.scale

        for ch in s:
            try:
                size = self.glyphSizeCache[ch]
            except KeyError:
                size = self.font.size(ch)
                self.glyphSizeCache[ch] = size

            w += size[0]
            h = max(size[1], h)

        return (w * scale, h * scale)

    def getHeight(self):
        return self.font.get_height() * self.scale

    def getLineSpacing(self):
        return self.font.get_linesize() * self.scale

    def setCustomGlyph(self, character, texture):
        texture.setFilter(GL_LINEAR, GL_LINEAR)
        texture.setRepeat(GL_CLAMP, GL_CLAMP)

        self.glyphCache[character] = (
            texture,
            (0.0, 0.0, texture.size[0], texture.size[1]),
        )

        s = 0.75 * self.getHeight() / float(texture.pixelSize[0])
        self.glyphSizeCache[character] = (
            texture.pixelSize[0] * s,
            texture.pixelSize[1] * s,
        )

    def _allocateGlyphTexture(self):
        max_tex = glGetInteger(GL_MAX_TEXTURE_SIZE)

        # Limite sensato para atlas de fontes
        ATLAS_SIZE = min(2048, max_tex)

        atlas = TextureAtlas(size=ATLAS_SIZE)
        self.atlases.append(atlas)
        self.glyphTextures.append(atlas)
        return atlas

    def getGlyph(self, ch):
        try:
            return self.glyphCache[ch]
        except KeyError:
            surface = self.font.render(ch, True, (255, 255, 255))

            if not self.glyphTextures:
                texture = self._allocateGlyphTexture()
            else:
                texture = self.glyphTextures[-1]

            try:
                coordinates = texture.add(surface)
            except TextureAtlasFullException:
                texture = self._allocateGlyphTexture()
                coordinates = texture.add(surface)

            self.glyphCache[ch] = (texture, coordinates)
            return self.glyphCache[ch]

    def _renderString(self, text, pos, direction, scale):
        if not text:
            return

        key = (text, scale)
        if key not in self.stringCache:
            currentTexture = None
            x, y = 0.0, 0.0

            vertices = numpy.empty((4 * len(text), 2), numpy.float32)
            texCoords = numpy.empty((4 * len(text), 2), numpy.float32)
            vertexCount = 0
            cacheEntry = []

            for ch in text:
                g, coords = self.getGlyph(ch)
                w, h = self.getStringSize(ch, scale=scale)
                tx1, ty1, tx2, ty2 = coords

                if currentTexture is None:
                    currentTexture = g

                if currentTexture != g:
                    cacheEntry.append(
                        (
                            currentTexture,
                            vertexCount,
                            vertices[:vertexCount].copy(),
                            texCoords[:vertexCount].copy(),
                        )
                    )
                    currentTexture = g
                    vertexCount = 0

                vertices[vertexCount : vertexCount + 4] = [
                    (x, y),
                    (x + w, y),
                    (x + w, y + h),
                    (x, y + h),
                ]

                texCoords[vertexCount : vertexCount + 4] = [
                    (tx1, ty2),
                    (tx2, ty2),
                    (tx2, ty1),
                    (tx1, ty1),
                ]

                vertexCount += 4
                x += w * direction[0]
                y += w * direction[1]

            cacheEntry.append(
                (
                    currentTexture,
                    vertexCount,
                    vertices[:vertexCount],
                    texCoords[:vertexCount],
                )
            )

            if len(self.stringCache) > self.stringCacheLimit:
                oldest = next(iter(self.stringCache))
                del self.stringCache[oldest]

            self.stringCache[key] = cacheEntry

        else:
            cacheEntry = self.stringCache[key]

        glPushMatrix()
        glTranslatef(pos[0], pos[1], 0)

        for texture, count, verts, uvs in cacheEntry:
            texture.bind()
            glVertexPointer(2, GL_FLOAT, 0, verts)
            glTexCoordPointer(2, GL_FLOAT, 0, uvs)
            glDrawArrays(GL_QUADS, 0, count)

        glPopMatrix()

    def render(self, text, pos=(0, 0), direction=(1, 0), scale=0.002):
        if not text:
            return

        # Salva TODO o estado relevante
        glPushAttrib(
            GL_ENABLE_BIT | GL_COLOR_BUFFER_BIT | GL_TEXTURE_BIT | GL_CURRENT_BIT
        )

        glEnable(GL_TEXTURE_2D)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

        glEnableClientState(GL_VERTEX_ARRAY)
        glEnableClientState(GL_TEXTURE_COORD_ARRAY)

        scale *= self.scale

        if self.reversed:
            text = "".join(reversed(text))

        if self.outline:
            glPushAttrib(GL_CURRENT_BIT)
            glColor4f(0, 0, 0, glGetFloatv(GL_CURRENT_COLOR)[3])
            self._renderString(
                text,
                (pos[0] + 0.003, pos[1] + 0.003),
                direction,
                scale,
            )
            glPopAttrib()

        self._renderString(text, pos, direction, scale)

        glDisableClientState(GL_VERTEX_ARRAY)
        glDisableClientState(GL_TEXTURE_COORD_ARRAY)

        # Restaura TUDO exatamente como estava
        glPopAttrib()
