#####################################################################
# -*- coding: iso-8859-1 -*-                                        #
#                                                                   #
# Frets on Fire                                                     #
# Copyright (C) 2006 Sami Ky�stil�                                  #
#                                                                   #
#####################################################################

import re
import os
import io
from xml import sax
from OpenGL.GL import *
from numpy import reshape, dot, transpose, identity, zeros, float32
from math import sin, cos

import Log
import Config
from Texture import Texture, TextureException

# Amanith support is now deprecated
# try:
#   import amanith
#   import SvgColors
#   haveAmanith    = True
# except ImportError:
#   Log.warn("PyAmanith not found, SVG support disabled.")
#   import DummyAmanith as amanith
#   haveAmanith    = False

import DummyAmanith as amanith

haveAmanith = True

# SvgColors era usado no Py2; aqui garantimos que não vai explodir caso
# o SVG use cores nomeadas (ex: "white", "black") e o dict não exista.
try:
    import SvgColors  # type: ignore
except Exception:

    class _SvgColorsFallback:
        colors = {}

    SvgColors = _SvgColorsFallback()  # type: ignore


# Add support for 'foo in attributes' syntax
# No Python 3, AttributesImpl normalmente já suporta __contains__,
# mas mantemos o fallback de forma compatível.
if not hasattr(sax.xmlreader.AttributesImpl, "__contains__"):

    def _attrs_contains(self, key):
        try:
            # attrs.get(key) retorna None se não existir
            return self.get(key) is not None
        except Exception:
            try:
                self.getValue(key)
                return True
            except Exception:
                return False

    sax.xmlreader.AttributesImpl.__contains__ = _attrs_contains  # type: ignore


#
#  Bugs and limitations:
#
#  - only the translate() and matrix() transforms are supported
#  - only paths are supported
#  - only constant color, linear gradient and radial gradient fill supported
#

Config.define(
    "opengl",
    "svgshaders",
    bool,
    False,
    text="Use OpenGL SVG shaders",
    options={False: "No", True: "Yes"},
)

LOW_QUALITY = amanith.G_LOW_RENDERING_QUALITY
NORMAL_QUALITY = amanith.G_NORMAL_RENDERING_QUALITY
HIGH_QUALITY = amanith.G_HIGH_RENDERING_QUALITY


class SvgGradient:
    def __init__(self, gradientDesc, transform):
        self.gradientDesc = gradientDesc
        self.transform = transform

    def applyTransform(self, transform):
        m = dot(transform.matrix, self.transform.matrix)
        self.gradientDesc.SetMatrix(transform.getGMatrix(m))


class SvgContext:
    def __init__(self, geometry):
        self.kernel = amanith.GKernel()
        self.geometry = geometry
        self.drawBoard = amanith.GOpenGLBoard(
            geometry[0],
            geometry[0] + geometry[2],
            geometry[1],
            geometry[1] + geometry[3],
        )
        self.drawBoard.SetShadersEnabled(Config.get("opengl", "svgshaders"))
        self.transform = SvgTransform()
        self.setGeometry(geometry)
        self.setProjection(geometry)

        # eat any possible OpenGL errors -- we can't handle them anyway
        try:
            glMatrixMode(GL_MODELVIEW)
        except Exception:
            Log.warn(
                "SVG renderer initialization failed; expect corrupted graphics. "
                "To fix this, upgrade your OpenGL drivers and set your display "
                "to 32 bit color precision."
            )

    def setGeometry(self, geometry=None):
        geometry = geometry or self.geometry
        self.drawBoard.SetViewport(geometry[0], geometry[1], geometry[2], geometry[3])
        self.transform.reset()
        self.transform.scale(geometry[2] / 640.0, geometry[3] / 480.0)

    def setProjection(self, geometry=None):
        geometry = geometry or self.geometry
        self.drawBoard.SetProjection(
            geometry[0],
            geometry[0] + geometry[2],
            geometry[1],
            geometry[1] + geometry[3],
        )
        self.geometry = geometry

    def setRenderingQuality(self, quality):
        # Ignored
        pass

    def getRenderingQuality(self):
        q = self.drawBoard.RenderingQuality()
        if q == amanith.G_LOW_RENDERING_QUALITY:
            return LOW_QUALITY
        elif q == amanith.G_NORMAL_RENDERING_QUALITY:
            return NORMAL_QUALITY
        return HIGH_QUALITY

    def clear(self, r=0, g=0, b=0, a=0):
        self.drawBoard.Clear(r, g, b, a)


class SvgRenderStyle:
    def __init__(self, baseStyle=None):
        self.strokeColor = None
        self.strokeWidth = None
        self.fillColor = None
        self.strokeLineJoin = None
        self.strokeOpacity = None
        self.fillOpacity = None

        if baseStyle:
            self.__dict__.update(baseStyle.__dict__)

    def parseStyle(self, style):
        s = {}
        for m in re.finditer(r"(.+?):\s*(.+?)(;|$)\s*", style):
            s[m.group(1)] = m.group(2)
        return s

    def parseColor(self, color, defs=None):
        if color.lower() == "none":
            return None

        try:
            return SvgColors.colors[color.lower()]
        except Exception:
            pass

        if color and color[0] == "#":
            color = color[1:]
            if len(color) == 3:
                return (
                    int(color[0], 16) / 15.0,
                    int(color[1], 16) / 15.0,
                    int(color[2], 16) / 15.0,
                    1.0,
                )
            return (
                int(color[0:2], 16) / 255.0,
                int(color[2:4], 16) / 255.0,
                int(color[4:6], 16) / 255.0,
                1.0,
            )
        else:
            if not defs:
                Log.warn("No patterns or gradients defined.")
                return None
            m = re.match(r"url\(#(.+)\)", color)
            if m:
                _id = m.group(1)
                if _id not in defs:
                    Log.warn("Pattern/gradient %s has not been defined." % _id)
                return defs.get(_id)

        return None

    # Python 3: __cmp__ não existe. A engine depende de comparar estilos
    # para agrupar strokes no cache, então implementamos __eq__/__ne__.
    def __eq__(self, other):
        if other is None:
            return False
        if not isinstance(other, SvgRenderStyle):
            return False
        return self.__dict__ == other.__dict__

    def __ne__(self, other):
        return not self.__eq__(other)

    def __repr__(self):
        return (
            "<SvgRenderStyle "
            + " ".join(["%s:%s" % (k, v) for k, v in self.__dict__.items()])
            + ">"
        )

    def applyAttributes(self, attrs, defs):
        style = attrs.get("style")
        if style:
            style = self.parseStyle(style)
            if "stroke" in style:
                self.strokeColor = self.parseColor(style["stroke"], defs)
            if "fill" in style:
                self.fillColor = self.parseColor(style["fill"], defs)
            if "stroke-width" in style:
                self.strokeWidth = float(style["stroke-width"].replace("px", ""))
            if "stroke-opacity" in style:
                self.strokeOpacity = float(style["stroke-opacity"])
            if "fill-opacity" in style:
                self.fillOpacity = float(style["fill-opacity"])
            if "stroke-linejoin" in style:
                j = style["stroke-linejoin"].lower()
                if j == "miter":
                    self.strokeLineJoin = amanith.G_MITER_JOIN
                elif j == "round":
                    self.strokeLineJoin = amanith.G_ROUND_JOIN
                elif j == "bevel":
                    self.strokeLineJoin = amanith.G_BEVEL_JOIN

    def apply(self, drawBoard, transform):
        if self.strokeColor is not None:
            if isinstance(self.strokeColor, SvgGradient):
                self.strokeColor.applyTransform(transform)
                drawBoard.SetStrokePaintType(amanith.G_GRADIENT_PAINT_TYPE)
                drawBoard.SetStrokeGradient(self.strokeColor.gradientDesc)
            else:
                drawBoard.SetStrokePaintType(amanith.G_COLOR_PAINT_TYPE)
                drawBoard.SetStrokeColor(*self.strokeColor)
            drawBoard.SetStrokeEnabled(True)
        else:
            drawBoard.SetStrokeEnabled(False)

        if self.fillColor is not None:
            if isinstance(self.fillColor, SvgGradient):
                self.fillColor.applyTransform(transform)
                drawBoard.SetFillPaintType(amanith.G_GRADIENT_PAINT_TYPE)
                drawBoard.SetFillGradient(self.fillColor.gradientDesc)
            else:
                drawBoard.SetFillPaintType(amanith.G_COLOR_PAINT_TYPE)
                drawBoard.SetFillColor(*self.fillColor)
            drawBoard.SetFillEnabled(True)
        else:
            drawBoard.SetFillEnabled(False)

        if self.strokeWidth is not None:
            drawBoard.SetStrokeWidth(self.strokeWidth)

        if self.strokeOpacity is not None:
            drawBoard.SetStrokeOpacity(self.strokeOpacity)

        if self.fillOpacity is not None:
            drawBoard.SetFillOpacity(self.fillOpacity)

        if self.strokeLineJoin is not None:
            drawBoard.SetStrokeJoinStyle(self.strokeLineJoin)


class SvgTransform:
    def __init__(self, baseTransform=None):
        self._gmatrix = amanith.GMatrix33()
        self.reset()

        if baseTransform:
            self.matrix = baseTransform.matrix.copy()

    def applyAttributes(self, attrs, key="transform"):
        transform = attrs.get(key)
        if transform:
            m = re.match(r"translate\(\s*(.+?)\s*,(.+?)\s*\)", transform)
            if m:
                dx, dy = [float(c) for c in m.groups()]
                self.matrix[0, 2] += dx
                self.matrix[1, 2] += dy

            m = re.match(
                r"matrix\(\s*" + r"\s*,\s*".join(["(.+?)"] * 6) + r"\s*\)", transform
            )
            if m:
                e = [float(c) for c in m.groups()]
                e = [e[0], e[2], e[4], e[1], e[3], e[5], 0, 0, 1]
                mm = reshape(e, (3, 3))
                self.matrix = dot(self.matrix, mm)

    def transform(self, transform):
        self.matrix = dot(self.matrix, transform.matrix)

    def reset(self):
        self.matrix = identity(3, float32)

    def translate(self, dx, dy):
        m = zeros((3, 3))
        m[0, 2] = dx
        m[1, 2] = dy
        self.matrix += m

    def rotate(self, angle):
        m = identity(3, float32)
        s = sin(angle)
        c = cos(angle)
        m[0, 0] = c
        m[0, 1] = -s
        m[1, 0] = s
        m[1, 1] = c
        self.matrix = dot(self.matrix, m)

    def scale(self, sx, sy):
        m = identity(3, float32)
        m[0, 0] = sx
        m[1, 1] = sy
        self.matrix = dot(self.matrix, m)

    def applyGL(self):
        # Interpret the 2D matrix as 3D
        m = self.matrix
        m = [
            m[0, 0],
            m[1, 0],
            0.0,
            0.0,
            m[0, 1],
            m[1, 1],
            0.0,
            0.0,
            0.0,
            0.0,
            1.0,
            0.0,
            m[0, 2],
            m[1, 2],
            0.0,
            1.0,
        ]
        glMultMatrixf(m)

    def getGMatrix(self, m):
        f = float
        self._gmatrix.Set(
            f(m[0, 0]),
            f(m[0, 1]),
            f(m[0, 2]),
            f(m[1, 0]),
            f(m[1, 1]),
            f(m[1, 2]),
            f(m[2, 0]),
            f(m[2, 1]),
            f(m[2, 2]),
        )
        return self._gmatrix

    def apply(self, drawBoard):
        drawBoard.SetModelViewMatrix(self.getGMatrix(self.matrix))


class SvgHandler(sax.ContentHandler):
    def __init__(self, drawBoard, cache):
        self.drawBoard = drawBoard
        self.styleStack = [SvgRenderStyle()]
        self.contextStack = [None]
        self.transformStack = [SvgTransform()]
        self.defs = {}
        self.cache = cache

    def startElement(self, name, attrs):
        style = SvgRenderStyle(self.style())
        style.applyAttributes(attrs, self.defs)
        self.styleStack.append(style)

        transform = SvgTransform(self.transform())
        transform.applyAttributes(attrs)
        self.transformStack.append(transform)

        try:
            f = "start" + name.capitalize()
            f = getattr(self, f)
        except AttributeError:
            return
        f(attrs)

    def endElement(self, name):
        try:
            f = "end" + name.capitalize()
            getattr(self, f)()
        except AttributeError:
            pass
        self.styleStack.pop()
        self.transformStack.pop()

    def startG(self, attrs):
        self.contextStack.append("g")

    def endG(self):
        self.contextStack.pop()

    def startDefs(self, attrs):
        self.contextStack.append("defs")

    def endDefs(self):
        self.contextStack.pop()

    def startMarker(self, attrs):
        self.contextStack.append("marker")

    def endMarker(self):
        self.contextStack.pop()

    def context(self):
        return self.contextStack[-1]

    def style(self):
        return self.styleStack[-1]

    def transform(self):
        return self.transformStack[-1]

    def startPath(self, attrs):
        if self.context() in ["g", None]:
            if "d" in attrs:
                self.style().apply(self.drawBoard, self.transform())
                self.transform().apply(self.drawBoard)
                d = str(attrs["d"])
                self.cache.addStroke(
                    self.style(),
                    self.transform(),
                    self.drawBoard.DrawPaths(d),
                )

    def createLinearGradient(self, attrs, keys):
        a = dict(attrs)
        if "x1" not in a or "x2" not in a or "y1" not in a or "y2" not in a:
            a["x1"] = a["y1"] = 0.0
            a["x2"] = a["y2"] = 1.0
        if "id" in a and "x1" in a and "x2" in a and "y1" in a and "y2" in a:
            transform = SvgTransform()
            if "gradientTransform" in a:
                transform.applyAttributes(a, key="gradientTransform")
            x1, y1, x2, y2 = [float(a[k]) for k in ["x1", "y1", "x2", "y2"]]
            return (
                a["id"],
                self.drawBoard.CreateLinearGradient((x1, y1), (x2, y2), keys),
                transform,
            )
        return None, None, None

    def createRadialGradient(self, attrs, keys):
        a = dict(attrs)
        if "cx" not in a or "cy" not in a or "fx" not in a or "fy" not in a:
            a["cx"] = a["cy"] = 0.0
            a["fx"] = a["fy"] = 1.0
        if (
            "id" in a
            and "cx" in a
            and "cy" in a
            and "fx" in a
            and "fy" in a
            and "r" in a
        ):
            transform = SvgTransform()
            if "gradientTransform" in a:
                transform.applyAttributes(a, key="gradientTransform")
            cx, cy, fx, fy, r = [float(a[k]) for k in ["cx", "cy", "fx", "fy", "r"]]
            return (
                a["id"],
                self.drawBoard.CreateRadialGradient((cx, cy), (fx, fy), r, keys),
                transform,
            )
        return None, None, None

    def startLineargradient(self, attrs):
        if self.context() == "defs":
            if "xlink:href" in attrs:
                _id = attrs["xlink:href"][1:]
                if _id not in self.defs:
                    Log.warn("Linear gradient %s has not been defined." % _id)
                else:
                    keys = self.defs[_id].gradientDesc.ColorKeys()
                    gid, grad, trans = self.createLinearGradient(attrs, keys)
                    self.defs[gid] = SvgGradient(grad, trans)
            else:
                self.contextStack.append("gradient")
                self.stops = []
                self.gradientAttrs = attrs

    def startRadialgradient(self, attrs):
        if self.context() == "defs":
            if "xlink:href" in attrs:
                _id = attrs["xlink:href"][1:]
                if _id not in self.defs:
                    Log.warn("Radial gradient %s has not been defined." % _id)
                else:
                    keys = self.defs[_id].gradientDesc.ColorKeys()
                    gid, grad, trans = self.createRadialGradient(attrs, keys)
                    self.defs[gid] = SvgGradient(grad, trans)
            else:
                self.contextStack.append("gradient")
                self.stops = []
                self.gradientAttrs = attrs

    def parseKeys(self, stops):
        keys = []
        for stop in self.stops:
            color, opacity, offset = None, None, None
            if "style" in stop:
                style = self.style().parseStyle(stop["style"])
                if "stop-color" in style:
                    color = self.style().parseColor(style["stop-color"])
                if "stop-opacity" in style:
                    opacity = float(style["stop-opacity"])
            if "offset" in stop:
                offset = float(stop["offset"])
            if offset is not None and (color is not None or opacity is not None):
                if opacity is None:
                    opacity = 1.0
                k = amanith.GKeyValue(offset, (color[0], color[1], color[2], opacity))
                keys.append(k)
        return keys

    def endLineargradient(self):
        if self.context() == "gradient":
            keys = self.parseKeys(self.stops)
            gid, grad, trans = self.createLinearGradient(self.gradientAttrs, keys)
            del self.stops
            del self.gradientAttrs
            if gid and grad:
                self.defs[gid] = SvgGradient(grad, trans)
            self.contextStack.pop()

    def endRadialgradient(self):
        if self.context() == "gradient":
            keys = self.parseKeys(self.stops)
            gid, grad, trans = self.createRadialGradient(self.gradientAttrs, keys)
            del self.stops
            del self.gradientAttrs
            if gid and grad:
                self.defs[gid] = SvgGradient(grad, trans)
            self.contextStack.pop()

    def startStop(self, attrs):
        if self.context() == "gradient":
            self.stops.append(attrs)


class SvgCache:
    def __init__(self, drawBoard):
        self.drawBoard = drawBoard
        self.displayList = []
        self.transforms = {}
        self.bank = drawBoard.CreateCacheBank()

    def beginCaching(self):
        self.drawBoard.SetCacheBank(self.bank)
        self.drawBoard.SetTargetMode(amanith.G_CACHE_MODE)

    def endCaching(self):
        self.drawBoard.SetTargetMode(amanith.G_COLOR_MODE)
        self.drawBoard.SetCacheBank(None)

    def addStroke(self, style, transform, slot):
        if self.displayList:
            lastStyle = self.displayList[-1][0]
        else:
            lastStyle = None

        self.transforms[slot] = transform

        if lastStyle == style:
            lastSlotStart, lastSlotEnd = self.displayList[-1][1][-1]
            if lastSlotEnd == slot - 1:
                self.displayList[-1][1][-1] = (lastSlotStart, slot)
            else:
                self.displayList[-1][1].append((slot, slot))
        else:
            self.displayList.append((style, [(slot, slot)]))

    def draw(self, baseTransform):
        self.drawBoard.SetCacheBank(self.bank)
        for style, slotList in self.displayList:
            transform = SvgTransform(baseTransform)
            transform.transform(self.transforms[slotList[0][0]])
            transform.apply(self.drawBoard)
            style.apply(self.drawBoard, transform)
            for firstSlot, lastSlot in slotList:
                self.drawBoard.DrawCacheSlots(firstSlot, lastSlot)
        self.drawBoard.SetCacheBank(None)

        # eat any possible OpenGL errors -- we can't handle them anyway
        try:
            glMatrixMode(GL_MODELVIEW)
        except Exception:
            pass


class SvgDrawing:
    def __init__(self, context, svgData):
        self.svgData = None
        self.texture = None
        self.context = context
        self.cache = None
        self.transform = SvgTransform()

        # Detect the type of data passed in
        # Py2 had `type(x) == file`; Py3 uses IOBase / file-like objects.
        if hasattr(svgData, "read"):
            data = svgData.read()
            if isinstance(data, bytes):
                data = data.decode("utf-8", errors="replace")
            self.svgData = data

        elif isinstance(svgData, str):
            bitmapFile = svgData.replace(".svg", ".png")

            # Load PNG files directly
            if svgData.endswith(".png"):
                self.texture = Texture(svgData)

            # Check whether we have a prerendered bitmap version of the SVG file
            elif svgData.endswith(".svg") and os.path.exists(bitmapFile):
                Log.debug(
                    "Loading cached bitmap '%s' instead of '%s'."
                    % (bitmapFile, svgData)
                )
                self.texture = Texture(bitmapFile)

            else:
                if not haveAmanith:
                    e = "PyAmanith support is deprecated and you are trying to load an SVG file."
                    Log.error(e)
                    raise RuntimeError(e)
                Log.debug("Loading SVG file '%s'." % (svgData))
                with open(svgData, "r", encoding="utf-8", errors="replace") as f:
                    self.svgData = f.read()

        # Validade: precisamos ter OU textura OU svgData
        if self.texture is None and self.svgData is None:
            if isinstance(svgData, str):
                e = "Unable to load texture/SVG for %s." % svgData
            else:
                e = "Unable to load texture/SVG data."
            Log.error(e)
            raise RuntimeError(e)

    def _cacheDrawing(self, drawBoard):
        self.cache.beginCaching()
        sax.parseString(self.svgData, SvgHandler(drawBoard, self.cache))
        self.cache.endCaching()
        del self.svgData

    def convertToTexture(self, width, height):
        # Mantido como no original (feature praticamente desativada),
        # mas sem explodir por lógica invertida.
        if self.texture:
            return

        e = "SVG drawing does not have a valid texture image."
        Log.error(e)
        raise RuntimeError(e)

        # try:
        #   self.texture = Texture()
        #   ...
        # except TextureException as e:
        #   Log.warn("Unable to convert SVG drawing to texture: %s" % str(e))

    def _getEffectiveTransform(self):
        transform = SvgTransform(self.transform)
        transform.transform(self.context.transform)
        return transform

    def _render(self, transform):
        glMatrixMode(GL_TEXTURE)
        glPushMatrix()
        glMatrixMode(GL_MODELVIEW)

        glPushAttrib(
            GL_ENABLE_BIT
            | GL_TEXTURE_BIT
            | GL_STENCIL_BUFFER_BIT
            | GL_TRANSFORM_BIT
            | GL_COLOR_BUFFER_BIT
            | GL_POLYGON_BIT
            | GL_CURRENT_BIT
            | GL_DEPTH_BUFFER_BIT
        )
        if not self.cache:
            self.cache = SvgCache(self.context.drawBoard)
            self._cacheDrawing(self.context.drawBoard)
        self.cache.draw(transform)
        glPopAttrib()

        glMatrixMode(GL_TEXTURE)
        glPopMatrix()
        glMatrixMode(GL_MODELVIEW)

    def draw(self, color=(1, 1, 1, 1)):
        glMatrixMode(GL_TEXTURE)
        glPushMatrix()
        glMatrixMode(GL_PROJECTION)
        glPushMatrix()
        self.context.setProjection()
        glMatrixMode(GL_MODELVIEW)
        glPushMatrix()

        transform = self._getEffectiveTransform()
        if self.texture:
            glLoadIdentity()
            transform.applyGL()

            glScalef(self.texture.pixelSize[0], self.texture.pixelSize[1], 1)
            glTranslatef(-0.5, -0.5, 0)
            glColor4f(*color)

            self.texture.bind()
            glEnable(GL_TEXTURE_2D)
            glBegin(GL_TRIANGLE_STRIP)
            glTexCoord2f(0.0, 1.0)
            glVertex2f(0.0, 1.0)
            glTexCoord2f(1.0, 1.0)
            glVertex2f(1.0, 1.0)
            glTexCoord2f(0.0, 0.0)
            glVertex2f(0.0, 0.0)
            glTexCoord2f(1.0, 0.0)
            glVertex2f(1.0, 0.0)
            glEnd()
            glDisable(GL_TEXTURE_2D)
        else:
            self._render(transform)

        glMatrixMode(GL_TEXTURE)
        glPopMatrix()
        glMatrixMode(GL_MODELVIEW)
        glPopMatrix()
        glMatrixMode(GL_PROJECTION)
        glPopMatrix()
        glMatrixMode(GL_MODELVIEW)
