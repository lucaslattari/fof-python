# src/Texture.py
#####################################################################
# -*- coding: iso-8859-1 -*-                                        #
#                                                                   #
# Frets on Fire                                                     #
# Copyright (C) 2006 Sami Ky�stil�                                  #
#####################################################################

import io
from queue import Queue, Empty

import pygame
from OpenGL.GL import *
from OpenGL.GLU import *

import Log
import Config

# Pillow
from PIL import Image
from PIL import (
    PngImagePlugin,
)  # noqa: F401 (mantido por compatibilidade / plugins internos)

Config.define("opengl", "supportfbo", bool, False)

try:
    # Extensão opcional, usada para checar suporte e funções EXT.
    from glew import *  # type: ignore  # noqa: F401,F403
except ImportError:
    # Log.warn("GLEWpy not found -> Emulating Render to texture functionality.")
    pass


class TextureException(Exception):
    pass


# A queue contendo pares (function, args) para limpar handles OpenGL deletados.
# As funções são chamadas na thread principal (contexto OpenGL válido).
cleanupQueue: "Queue[tuple]" = Queue()


class Framebuffer:
    fboSupported = None

    def __init__(self, texture, width, height, generateMipmap=False):
        # Garantir ints Python nativos (evita overflow numpy)
        width = int(width)
        height = int(height)

        # Sanidade básica (protege OpenGL de crash fatal)
        if width <= 0 or height <= 0:
            raise TextureException(f"Invalid framebuffer size: {width}x{height}")

        # Limite conservador (compatível com GPUs antigas)
        if width > 8192 or height > 8192:
            raise TextureException(f"Framebuffer too large: {width}x{height}")

        self.emulated = not self._fboSupported()
        self.size = (width, height)
        self.colorbuf = texture
        self.generateMipmap = generateMipmap
        self.fb = 0
        self.depthbuf = 0
        self.stencilbuf = 0

        if self.emulated:
            # Em modo emulado, só aceitamos POT (power-of-two), como no original.
            if (width & (width - 1)) or (height & (height - 1)):
                raise TextureException(
                    "Only power-of-two render target textures are supported when frame buffer objects support is missing."
                )
        else:
            # Essas funções EXT vêm do PyOpenGL quando a extensão existe.
            self.fb = glGenFramebuffersEXT(1)[0]
            self.depthbuf = glGenRenderbuffersEXT(1)[0]
            self.stencilbuf = glGenRenderbuffersEXT(1)[0]
            glBindFramebufferEXT(GL_FRAMEBUFFER_EXT, self.fb)
            self._checkError()

        # Inicializa a textura alvo (RGBA vazia)
        glBindTexture(GL_TEXTURE_2D, self.colorbuf)
        glTexParameterf(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)

        buf_size = width * height * 4
        buffer = b"\x00" * buf_size

        # PyOpenGL não aceita NULL direto, então mandamos um buffer vazio
        glTexImage2D(
            GL_TEXTURE_2D,
            0,
            GL_RGBA,
            width,
            height,
            0,
            GL_RGBA,
            GL_UNSIGNED_BYTE,
            buffer,
        )
        self._checkError()

        if self.emulated:
            return

        glBindFramebufferEXT(GL_FRAMEBUFFER_EXT, self.fb)

        try:
            glFramebufferTexture2DEXT(
                GL_FRAMEBUFFER_EXT,
                GL_COLOR_ATTACHMENT0_EXT,
                GL_TEXTURE_2D,
                self.colorbuf,
                0,
            )
            self._checkError()

            # Em alguns drivers antigos, stencil precisava ser "packed" com depth
            if "glewGetExtension" in globals() and glewGetExtension(
                "GL_NV_packed_depth_stencil"
            ):
                GL_DEPTH_STENCIL_EXT = 0x84F9

                glBindRenderbufferEXT(GL_RENDERBUFFER_EXT, self.depthbuf)
                glRenderbufferStorageEXT(
                    GL_RENDERBUFFER_EXT, GL_DEPTH_STENCIL_EXT, width, height
                )
                glFramebufferRenderbufferEXT(
                    GL_FRAMEBUFFER_EXT,
                    GL_DEPTH_ATTACHMENT_EXT,
                    GL_RENDERBUFFER_EXT,
                    self.depthbuf,
                )
                self._checkError()
            else:
                glBindRenderbufferEXT(GL_RENDERBUFFER_EXT, self.depthbuf)
                glRenderbufferStorageEXT(
                    GL_RENDERBUFFER_EXT, GL_DEPTH_COMPONENT24, width, height
                )
                glFramebufferRenderbufferEXT(
                    GL_FRAMEBUFFER_EXT,
                    GL_DEPTH_ATTACHMENT_EXT,
                    GL_RENDERBUFFER_EXT,
                    self.depthbuf,
                )
                self._checkError()

                glBindRenderbufferEXT(GL_RENDERBUFFER_EXT, self.stencilbuf)
                glRenderbufferStorageEXT(
                    GL_RENDERBUFFER_EXT, GL_STENCIL_INDEX_EXT, width, height
                )
                glFramebufferRenderbufferEXT(
                    GL_FRAMEBUFFER_EXT,
                    GL_STENCIL_ATTACHMENT_EXT,
                    GL_RENDERBUFFER_EXT,
                    self.stencilbuf,
                )
                self._checkError()
        finally:
            glBindFramebufferEXT(GL_FRAMEBUFFER_EXT, 0)

        print("[FBO]", "size =", width, "x", height, "emulated =", self.emulated)

    def __del__(self):
        # Enfileira a deleção para acontecer com contexto OpenGL válido.
        try:
            if not self.emulated:
                # Preferível: deletar renderbuffers e framebuffer com as funções corretas.
                if "glDeleteRenderbuffersEXT" in globals():
                    cleanupQueue.put(
                        (
                            glDeleteRenderbuffersEXT,
                            (2, [self.depthbuf, self.stencilbuf]),
                        )
                    )
                if "glDeleteFramebuffersEXT" in globals():
                    cleanupQueue.put((glDeleteFramebuffersEXT, (1, [self.fb])))
                else:
                    # Fallback bem conservador (não ideal, mas evita crash em setups estranhos)
                    cleanupQueue.put(
                        (
                            glDeleteBuffers,
                            (3, [self.depthbuf, self.stencilbuf, self.fb]),
                        )
                    )
        except NameError:
            pass

    def _fboSupported(self):
        if Framebuffer.fboSupported is not None:
            return Framebuffer.fboSupported

        Framebuffer.fboSupported = False

        if not Config.get("opengl", "supportfbo"):
            Log.warn("Frame buffer object support disabled in configuration.")
            return False

        if "glewGetExtension" not in globals():
            Log.warn("GLEWpy not found, so render to texture functionality disabled.")
            return False

        glewInit()

        if not glewGetExtension("GL_EXT_framebuffer_object"):
            Log.warn(
                "No support for framebuffer objects, so render to texture functionality disabled."
            )
            return False

        # Original: bloqueia ATI antigos por problemas com stencil
        try:
            vendor = glGetString(GL_VENDOR)
            if vendor and vendor.decode("ascii", "ignore") == "ATI Technologies Inc.":
                Log.warn(
                    "Frame buffer object support disabled until ATI learns to make proper OpenGL drivers (no stencil support)."
                )
                return False
        except Exception:
            pass

        Framebuffer.fboSupported = True
        return True

    def _checkError(self):
        # Original tinha check via glGetError, mas foi desativado.
        # Mantemos assim para não introduzir overhead / mudanças de comportamento.
        return

    def setAsRenderTarget(self):
        if not self.emulated:
            glBindTexture(GL_TEXTURE_2D, 0)
            glBindFramebufferEXT(GL_FRAMEBUFFER_EXT, self.fb)
            self._checkError()

    def resetDefaultRenderTarget(self):
        glTexParameterf(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        if not self.emulated:
            glBindFramebufferEXT(GL_FRAMEBUFFER_EXT, 0)
            glBindTexture(GL_TEXTURE_2D, self.colorbuf)
            if self.generateMipmap:
                if "glGenerateMipmapEXT" in globals():
                    glGenerateMipmapEXT(GL_TEXTURE_2D)
                glTexParameterf(
                    GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR_MIPMAP_LINEAR
                )
            else:
                glTexParameterf(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        else:
            glBindTexture(GL_TEXTURE_2D, self.colorbuf)
            glCopyTexSubImage2D(
                GL_TEXTURE_2D, 0, 0, 0, 0, 0, self.size[0], self.size[1]
            )
            glTexParameterf(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)


class Texture:
    """Representa uma textura OpenGL, opcionalmente carregada do disco via Pillow."""

    def __init__(self, name=None, target=GL_TEXTURE_2D):
        # Limpa pendências de deleção (precisa ocorrer no thread/contexto OpenGL)
        while True:
            try:
                func, args = cleanupQueue.get_nowait()
                func(*args)
            except Empty:
                break
            except Exception:
                # Não deixa um cleanup quebrado travar o jogo
                break

        self.texture = glGenTextures(1)
        self.texEnv = GL_MODULATE
        self.glTarget = target
        self.framebuffer = None

        self.setDefaults()
        self.name = name

        if name:
            self.loadFile(name)

    def loadFile(self, name):
        """Carrega a textura do disco via Pillow."""
        self.loadImage(Image.open(name))
        self.name = name

    def loadImage(self, image: Image.Image):
        """Carrega a textura a partir de um PIL.Image."""
        image = image.transpose(Image.FLIP_TOP_BOTTOM)

        if image.mode == "RGBA":
            data = image.tobytes("raw", "RGBA", 0, -1)
            self.loadRaw(image.size, data, GL_RGBA, 4)
        elif image.mode == "RGB":
            data = image.tobytes("raw", "RGB", 0, -1)
            self.loadRaw(image.size, data, GL_RGB, 3)
        elif image.mode == "L":
            data = image.tobytes("raw", "L", 0, -1)
            self.loadRaw(image.size, data, GL_LUMINANCE, 1)
        else:
            raise TextureException("Unsupported image mode '%s'" % image.mode)

    def prepareRenderTarget(self, width, height, generateMipmap=True):
        self.framebuffer = Framebuffer(self.texture, width, height, generateMipmap)
        self.pixelSize = (width, height)
        self.size = (1.0, 1.0)

    def setAsRenderTarget(self):
        assert self.framebuffer
        self.framebuffer.setAsRenderTarget()

    def resetDefaultRenderTarget(self):
        assert self.framebuffer
        self.framebuffer.resetDefaultRenderTarget()

    def nextPowerOfTwo(self, n):
        m = 1
        while m < n:
            m <<= 1
        return m

    def loadSurface(self, surface, monochrome=False, alphaChannel=False):
        """Carrega textura a partir de um pygame.Surface."""

        # faz POT
        self.pixelSize = w, h = surface.get_size()
        w2, h2 = [self.nextPowerOfTwo(x) for x in (w, h)]
        if w != w2 or h != h2:
            s = pygame.Surface((w2, h2), pygame.SRCALPHA, 32)
            s.blit(surface, (0, h2 - h))
            surface = s

        if monochrome:
            # pygame não tem modo L; converte via Pillow
            raw = pygame.image.tostring(surface, "RGB")
            img = Image.frombytes("RGB", surface.get_size(), raw).convert("L")
            data = img.tobytes("raw", "L", 0, -1)
            self.loadRaw(surface.get_size(), data, GL_LUMINANCE, GL_INTENSITY8)
        else:
            if alphaChannel:
                data = pygame.image.tostring(surface, "RGBA", True)
                self.loadRaw(surface.get_size(), data, GL_RGBA, 4)
            else:
                data = pygame.image.tostring(surface, "RGB", True)
                self.loadRaw(surface.get_size(), data, GL_RGB, 3)

        self.size = (w / float(w2), h / float(h2))

    def loadSubsurface(
        self, surface, position=(0, 0), monochrome=False, alphaChannel=False
    ):
        """Carrega um patch em sub-região da textura (atlas)."""

        if monochrome:
            raw = pygame.image.tostring(surface, "RGB")
            img = Image.frombytes("RGB", surface.get_size(), raw).convert("L")
            data = img.tobytes("raw", "L", 0, -1)
            self.loadSubRaw(surface.get_size(), position, data, GL_INTENSITY8)
        else:
            if alphaChannel:
                data = pygame.image.tostring(surface, "RGBA", True)
                self.loadSubRaw(surface.get_size(), position, data, GL_RGBA)
            else:
                data = pygame.image.tostring(surface, "RGB", True)
                self.loadSubRaw(surface.get_size(), position, data, GL_RGB)

    def loadRaw(self, size, data: bytes, format, components):
        """Carrega uma imagem raw."""
        self.pixelSize = size
        self.size = (1.0, 1.0)
        self.format = format
        self.components = components
        (w, h) = size

        self.bind()
        glPixelStorei(GL_UNPACK_ALIGNMENT, 1)
        gluBuild2DMipmaps(
            self.glTarget, components, w, h, format, GL_UNSIGNED_BYTE, data
        )

    def loadSubRaw(self, size, position, data: bytes, format):
        self.bind()
        glPixelStorei(GL_UNPACK_ALIGNMENT, 1)
        glTexSubImage2D(
            self.glTarget,
            0,
            position[0],
            position[1],
            size[0],
            size[1],
            format,
            GL_UNSIGNED_BYTE,
            data,
        )

    def loadEmpty(self, size, format):
        # Normaliza tamanho (evita numpy / float / overflow)
        width = int(size[0])
        height = int(size[1])

        if width <= 0 or height <= 0:
            raise TextureException(f"Invalid texture size: {width}x{height}")

        # Limite conservador (compatível com GPUs antigas)
        if width > 8192 or height > 8192:
            raise TextureException(f"Texture too large: {width}x{height}")

        self.pixelSize = (width, height)
        self.size = (1.0, 1.0)
        self.format = format

        self.bind()

        buf_size = width * height * 4
        buffer = b"\x00" * buf_size

        glTexImage2D(
            GL_TEXTURE_2D,
            0,
            format,
            width,
            height,
            0,
            format,
            GL_UNSIGNED_BYTE,
            buffer,
        )

        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)

    def setDefaults(self):
        """Seta opções default OpenGL."""
        self.setRepeat()
        self.setFilter()
        glHint(GL_PERSPECTIVE_CORRECTION_HINT, GL_NICEST)

    def setRepeat(self, u=GL_CLAMP, v=GL_CLAMP):
        self.bind()
        glTexParameteri(self.glTarget, GL_TEXTURE_WRAP_S, u)
        glTexParameteri(self.glTarget, GL_TEXTURE_WRAP_T, v)

    def setFilter(self, min=GL_LINEAR_MIPMAP_LINEAR, mag=GL_LINEAR):
        self.bind()
        glTexParameteri(self.glTarget, GL_TEXTURE_MIN_FILTER, min)
        glTexParameteri(self.glTarget, GL_TEXTURE_MAG_FILTER, mag)

    def __del__(self):
        # Enfileira deleção da textura
        try:
            cleanupQueue.put((glDeleteTextures, ([self.texture],)))
        except NameError:
            pass

    def bind(self, glTarget=None):
        """Bind da textura no contexto OpenGL."""
        if not glTarget:
            glTarget = self.glTarget
        glBindTexture(glTarget, self.texture)
        glTexEnvf(GL_TEXTURE_ENV, GL_TEXTURE_ENV_MODE, self.texEnv)


#
# Texture atlas
#
TEXTURE_ATLAS_SIZE = 1024


class TextureAtlasFullException(Exception):
    pass


class TextureAtlas(object):
    def __init__(self, size=TEXTURE_ATLAS_SIZE):
        self.texture = Texture()
        self.cursor = (0, 0)
        self.rowHeight = 0
        self.surfaceCount = 0
        self.texture.loadEmpty((size, size), GL_RGBA)
        self.texture.setFilter(GL_LINEAR, GL_LINEAR)
        self.texture.setRepeat(GL_CLAMP_TO_EDGE, GL_CLAMP_TO_EDGE)
        self.texture.texEnv = GL_MODULATE

    def add(self, surface, margin=0):
        w, h = surface.get_size()
        x, y = self.cursor

        w += margin
        h += margin

        if w > self.texture.pixelSize[0] or h > self.texture.pixelSize[1]:
            raise ValueError("Surface is too big to fit into atlas.")

        if x + w >= self.texture.pixelSize[0]:
            x = 0
            y += self.rowHeight
            self.rowHeight = 0

        if y + h >= self.texture.pixelSize[1]:
            Log.debug(
                "Texture atlas %s full after %d surfaces."
                % (self.texture.pixelSize, self.surfaceCount)
            )
            raise TextureAtlasFullException()

        self.texture.loadSubsurface(surface, position=(x, y), alphaChannel=True)

        self.surfaceCount += 1
        self.rowHeight = max(self.rowHeight, h)
        self.cursor = (x + w, y + h)

        # coordenadas normalizadas
        w -= margin
        h -= margin
        return (
            x / float(self.texture.pixelSize[0]),
            y / float(self.texture.pixelSize[1]),
            (x + w) / float(self.texture.pixelSize[0]),
            (y + h) / float(self.texture.pixelSize[1]),
        )

    def bind(self):
        self.texture.bind()
