# -*- coding: iso-8859-1 -*-
#####################################################################
# Frets on Fire
# Legacy-compatible View (Py3 port + optional debug hooks)
#
# Debug hooks (optional):
#   - layer._debugSticky = True       -> not removed by popAllLayers()
#   - layer._debugAlwaysOnTop = True  -> kept above other layers
#####################################################################

from __future__ import annotations

# IMPORTANT: keep star imports for legacy compatibility.
# Some modules may rely on "from View import *" exporting OpenGL symbols.
from OpenGL.GL import *  # noqa: F403,F401
from OpenGL.GLU import *  # noqa: F403,F401

import Log
from Task import Task


class Layer(Task):
    def render(self, visibility, topMost):
        pass

    def shown(self):
        pass

    def hidden(self):
        pass

    def run(self, ticks):
        pass

    def isBackgroundLayer(self):
        return False


class BackgroundLayer(Layer):
    def isBackgroundLayer(self):
        return True


class View(Task):
    def __init__(self, engine, geometry=None):
        Task.__init__(self)

        self.engine = engine

        self.layers = []
        self.incoming = []
        self.outgoing = []
        self.visibility = {}
        self.transitionTime = 512.0

        self.geometry = geometry or glGetIntegerv(GL_VIEWPORT)  # noqa: F405
        self.savedGeometry = None

        w = float(self.geometry[2] - self.geometry[0])
        h = float(self.geometry[3] - self.geometry[1])
        self.aspectRatio = (w / h) if h else 1.0

    # -------------------------
    # Debug helpers (optional)
    # -------------------------

    def _is_sticky(self, layer):
        return bool(getattr(layer, "_debugSticky", False))

    def _is_always_on_top(self, layer):
        return bool(getattr(layer, "_debugAlwaysOnTop", False))

    def _reorder_always_on_top(self):
        tops = [l for l in self.layers if self._is_always_on_top(l)]
        if not tops:
            return
        self.layers = [l for l in self.layers if l not in tops] + tops

    # -------------------------
    # Stack control
    # -------------------------

    def pushLayer(self, layer):
        Log.debug("View: Push: %s" % layer.__class__.__name__)

        if layer not in self.layers:
            self.layers.append(layer)
            self.incoming.append(layer)
            self.visibility[layer] = 0.0
            layer.shown()
        elif layer in self.outgoing:
            layer.hidden()
            layer.shown()
            self.outgoing.remove(layer)

        # Keep debug-top layers on top.
        self._reorder_always_on_top()

        self.engine.addTask(layer)

    def topLayer(self):
        for layer in reversed(list(self.layers)):
            if layer not in self.outgoing:
                return layer
        return None

    def popLayer(self, layer):
        Log.debug("View: Pop: %s" % layer.__class__.__name__)

        if layer in self.incoming:
            self.incoming.remove(layer)
        if layer in self.layers and layer not in self.outgoing:
            self.outgoing.append(layer)

    def popAllLayers(self):
        Log.debug("View: Pop all")
        for l in list(self.layers):
            if self._is_sticky(l):
                continue
            self.popLayer(l)

    def isTransitionInProgress(self):
        return bool(self.incoming or self.outgoing)

    # -------------------------
    # Transition update
    # -------------------------

    def run(self, ticks):
        if not self.layers:
            return

        topLayer = self.topLayer()
        t = float(ticks) / float(self.transitionTime) if self.transitionTime else 1.0

        for layer in list(self.layers):
            if layer not in self.visibility:
                continue

            fade_out = (layer in self.outgoing) or (
                layer is not topLayer and not layer.isBackgroundLayer()
            )

            if fade_out:
                if self.visibility[layer] > 0.0:
                    self.visibility[layer] = max(0.0, self.visibility[layer] - t)
                else:
                    self.visibility[layer] = 0.0

                    if layer in self.outgoing:
                        self.outgoing.remove(layer)
                        if layer in self.layers:
                            self.layers.remove(layer)
                        if layer in self.visibility:
                            del self.visibility[layer]
                        self.engine.removeTask(layer)
                        layer.hidden()

                    if layer in self.incoming:
                        self.incoming.remove(layer)

            else:
                if self.visibility[layer] < 1.0:
                    self.visibility[layer] = min(1.0, self.visibility[layer] + t)
                else:
                    self.visibility[layer] = 1.0
                    if layer in self.incoming:
                        self.incoming.remove(layer)

        self._reorder_always_on_top()

    # -------------------------
    # Projection / geometry (legacy-compatible)
    # -------------------------

    def setOrthogonalProjection(self, normalize=True, yIsDown=True):
        glMatrixMode(GL_PROJECTION)  # noqa: F405
        glPushMatrix()  # noqa: F405
        glLoadIdentity()  # noqa: F405

        viewport = glGetIntegerv(GL_VIEWPORT)  # noqa: F405
        if normalize:
            w = float(viewport[2] - viewport[0])
            h = float(viewport[3] - viewport[1]) or 1.0
            h *= (w / h) / (4.0 / 3.0)
            viewport = [0, 0, 1, h / w]

        if yIsDown:
            glOrtho(  # noqa: F405
                viewport[0],
                viewport[2] - viewport[0],
                viewport[3] - viewport[1],
                viewport[1],
                -100,
                100,
            )
        else:
            glOrtho(  # noqa: F405
                viewport[0],
                viewport[2] - viewport[0],
                viewport[1],
                viewport[3] - viewport[1],
                -100,
                100,
            )

        glMatrixMode(GL_MODELVIEW)  # noqa: F405
        glPushMatrix()  # noqa: F405
        glLoadIdentity()  # noqa: F405

    def resetProjection(self):
        glMatrixMode(GL_PROJECTION)  # noqa: F405
        glPopMatrix()  # noqa: F405
        glMatrixMode(GL_MODELVIEW)  # noqa: F405
        glPopMatrix()  # noqa: F405

    def setGeometry(self, geometry):
        viewport = glGetIntegerv(GL_VIEWPORT)  # noqa: F405
        w = float(viewport[2] - viewport[0])
        h = float(viewport[3] - viewport[1])
        s = (w, h, w, h)

        fixed = []
        for i, coord in enumerate(geometry):
            if isinstance(coord, float):
                fixed.append(int(s[i] * coord))
            else:
                fixed.append(int(coord))
        geometry = tuple(fixed)

        self.savedGeometry, self.geometry = viewport, geometry
        glViewport(*geometry)  # noqa: F405
        glScissor(*geometry)  # noqa: F405

    def resetGeometry(self):
        assert self.savedGeometry is not None

        self.savedGeometry, geometry = None, self.savedGeometry
        self.geometry = geometry
        glViewport(*geometry)  # noqa: F405
        glScissor(*geometry)  # noqa: F405

    def render(self):
        if not self.layers:
            return
        last = self.layers[-1]
        for layer in self.layers:
            layer.render(self.visibility.get(layer, 0.0), layer is last)
