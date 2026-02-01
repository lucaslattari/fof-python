# src/Stage.py
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

import configparser
from OpenGL.GL import *
import math

import Log
import Theme


class Layer(object):
    """
    A graphical stage layer that can have a number of animation effects associated with it.
    """

    def __init__(self, stage, drawing):
        """
        Constructor.

        @param stage:     Containing Stage
        @param drawing:   SvgDrawing for this layer. Make sure this drawing is rendered to
                          a texture for performance reasons.
        """
        self.stage = stage
        self.drawing = drawing
        self.position = (0.0, 0.0)
        self.angle = 0.0
        self.scale = (1.0, 1.0)
        self.color = (1.0, 1.0, 1.0, 1.0)
        self.srcBlending = GL_SRC_ALPHA
        self.dstBlending = GL_ONE_MINUS_SRC_ALPHA
        self.effects = []

    def render(self, visibility):
        """
        Render the layer.

        @param visibility:  Floating point visibility factor (1 = opaque, 0 = invisibile)
        """
        w, h = self.stage.engine.view.geometry[2:4]
        v = 1.0 - visibility**2

        self.drawing.transform.reset()
        self.drawing.transform.translate(w / 2, h / 2)

        if v > 0.01:
            # alpha segue a visibilidade
            self.color = (self.color[0], self.color[1], self.color[2], visibility)
            if self.position[0] < -0.25:
                self.drawing.transform.translate(-v * w, 0)
            elif self.position[0] > 0.25:
                self.drawing.transform.translate(v * w, 0)

        self.drawing.transform.scale(self.scale[0], -self.scale[1])
        self.drawing.transform.translate(
            self.position[0] * w / 2, -self.position[1] * h / 2
        )
        self.drawing.transform.rotate(self.angle)

        # Blend in all the effects
        for effect in self.effects:
            effect.apply()

        glBlendFunc(self.srcBlending, self.dstBlending)
        self.drawing.draw(color=self.color)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)


class Effect(object):
    """
    An animation effect that can be attached to a Layer.
    """

    def __init__(self, layer, options):
        """
        Constructor.

        @param layer:     Layer to attach this effect to.
        @param options:   Effect options (default in parens):
                            intensity - Floating point effect intensity (1.0)
                            trigger   - Effect trigger, one of "none", "beat",
                                        "quarterbeat", "pick", "miss" ("none")
                            period    - Trigger period in ms (500.0)
                            delay     - Trigger delay in periods (0.0)
                            profile   - Trigger profile, one of "step", "linstep",
                                        "smoothstep"
        """
        self.layer = layer
        self.stage = layer.stage
        self.intensity = float(options.get("intensity", 1.0))

        trigger_name = options.get("trigger", "none")
        self.trigger = getattr(
            self, "trigger" + trigger_name.capitalize(), self.triggerNone
        )

        self.period = float(options.get("period", 500.0))
        self.delay = float(options.get("delay", 0.0))

        prof_name = options.get("profile", "linstep")
        self.triggerProf = getattr(self, prof_name, self.linstep)

    def apply(self):
        pass

    def triggerNone(self):
        return 0.0

    def triggerBeat(self):
        if not self.stage.lastBeatPos:
            return 0.0
        t = self.stage.pos - self.delay * self.stage.beatPeriod - self.stage.lastBeatPos
        return self.intensity * (1.0 - self.triggerProf(0, self.stage.beatPeriod, t))

    def triggerQuarterbeat(self):
        if not self.stage.lastQuarterBeatPos:
            return 0.0
        t = (
            self.stage.pos
            - self.delay * (self.stage.beatPeriod / 4.0)
            - self.stage.lastQuarterBeatPos
        )
        return self.intensity * (
            1.0 - self.triggerProf(0, self.stage.beatPeriod / 4.0, t)
        )

    def triggerPick(self):
        if not self.stage.lastPickPos:
            return 0.0
        t = self.stage.pos - self.delay * self.period - self.stage.lastPickPos
        return self.intensity * (1.0 - self.triggerProf(0, self.period, t))

    def triggerMiss(self):
        if not self.stage.lastMissPos:
            return 0.0
        t = self.stage.pos - self.delay * self.period - self.stage.lastMissPos
        return self.intensity * (1.0 - self.triggerProf(0, self.period, t))

    def step(self, threshold, x):
        return 1 if x > threshold else 0

    def linstep(self, minv, maxv, x):
        if x < minv:
            return 0.0
        if x > maxv:
            return 1.0
        return float(x - minv) / float(maxv - minv)

    def smoothstep(self, minv, maxv, x):
        if x < minv:
            return 0.0
        if x > maxv:
            return 1.0

        def f(xx):
            return -2 * xx**3 + 3 * xx**2

        return f(float(x - minv) / float(maxv - minv))

    def sinstep(self, minv, maxv, x):
        return math.cos(math.pi * (1.0 - self.linstep(minv, maxv, x)))

    def getNoteColor(self, note):
        if note >= len(Theme.fretColors) - 1:
            return Theme.fretColors[-1]
        elif note <= 0:
            return Theme.fretColors[0]
        f2 = note % 1.0
        f1 = 1.0 - f2
        c1 = Theme.fretColors[int(note)]
        c2 = Theme.fretColors[int(note) + 1]
        return (
            c1[0] * f1 + c2[0] * f2,
            c1[1] * f1 + c2[1] * f2,
            c1[2] * f1 + c2[2] * f2,
        )


class LightEffect(Effect):
    def __init__(self, layer, options):
        super().__init__(layer, options)
        self.lightNumber = int(options.get("light_number", 0))
        self.ambient = float(options.get("ambient", 0.5))
        self.contrast = float(options.get("contrast", 0.5))

    def apply(self):
        if len(self.stage.averageNotes) < self.lightNumber + 2:
            self.layer.color = (0.0, 0.0, 0.0, 0.0)
            return

        t = self.trigger()
        t = self.ambient + self.contrast * t
        c = self.getNoteColor(self.stage.averageNotes[self.lightNumber])
        self.layer.color = (c[0] * t, c[1] * t, c[2] * t, self.intensity)


class RotateEffect(Effect):
    def __init__(self, layer, options):
        super().__init__(layer, options)
        self.angle = math.pi / 180.0 * float(options.get("angle", 45))

    def apply(self):
        if not self.stage.lastMissPos:
            return
        t = self.trigger()
        self.layer.drawing.transform.rotate(t * self.angle)


class WiggleEffect(Effect):
    def __init__(self, layer, options):
        super().__init__(layer, options)
        self.freq = float(options.get("frequency", 6))
        self.xmag = float(options.get("xmagnitude", 0.1))
        self.ymag = float(options.get("ymagnitude", 0.1))

    def apply(self):
        t = self.trigger()
        w, h = self.stage.engine.view.geometry[2:4]
        p = t * 2 * math.pi * self.freq
        s, c = t * math.sin(p), t * math.cos(p)
        self.layer.drawing.transform.translate(self.xmag * w * s, self.ymag * h * c)


class ScaleEffect(Effect):
    def __init__(self, layer, options):
        super().__init__(layer, options)
        self.xmag = float(options.get("xmagnitude", 0.1))
        self.ymag = float(options.get("ymagnitude", 0.1))

    def apply(self):
        t = self.trigger()
        self.layer.drawing.transform.scale(1.0 + self.xmag * t, 1.0 + self.ymag * t)


class Stage(object):
    def __init__(self, guitarScene, configFileName):
        self.scene = guitarScene
        self.engine = guitarScene.engine
        self.config = configparser.ConfigParser()
        self.backgroundLayers = []
        self.foregroundLayers = []
        self.textures = {}
        self.reset()

        # encoding explícito para bater com os .ini antigos do projeto
        try:
            self.config.read(configFileName, encoding="iso-8859-1")
        except TypeError:
            # fallback ultra-conservador (caso raro de ConfigParser custom)
            self.config.read(configFileName)

        # Build the layers
        for i in range(32):
            section = f"layer{i}"
            if not self.config.has_section(section):
                continue

            def get(value, typ=str, default=None):
                if self.config.has_option(section, value):
                    try:
                        return typ(self.config.get(section, value))
                    except Exception:
                        return default
                return default

            xres = get("xres", int, 256)
            yres = get("yres", int, 256)
            texture = get("texture", str, None)

            if not texture:
                Log.warn(f"Stage: missing texture in [{section}]")
                continue

            try:
                drawing = self.textures[texture]
            except KeyError:
                drawing = self.engine.loadSvgDrawing(
                    self, None, texture, textureSize=(xres, yres)
                )
                self.textures[texture] = drawing

            layer = Layer(self, drawing)

            layer.position = (get("xpos", float, 0.0), get("ypos", float, 0.0))
            layer.scale = (get("xscale", float, 1.0), get("yscale", float, 1.0))
            layer.angle = math.pi * get("angle", float, 0.0) / 180.0

            src_name = get("src_blending", str, "src_alpha").upper()
            dst_name = get("dst_blending", str, "one_minus_src_alpha").upper()
            layer.srcBlending = globals().get(f"GL_{src_name}", GL_SRC_ALPHA)
            layer.dstBlending = globals().get(f"GL_{dst_name}", GL_ONE_MINUS_SRC_ALPHA)

            layer.color = (
                get("color_r", float, 1.0),
                get("color_g", float, 1.0),
                get("color_b", float, 1.0),
                get("color_a", float, 1.0),
            )

            # Load any effects
            fxClasses = {
                "light": LightEffect,
                "rotate": RotateEffect,
                "wiggle": WiggleEffect,
                "scale": ScaleEffect,
            }

            for j in range(32):
                fxSection = f"layer{i}:fx{j}"
                if not self.config.has_section(fxSection):
                    continue

                fx_type = self.config.get(fxSection, "type")

                if fx_type not in fxClasses:
                    continue

                opts = self.config.options(fxSection)
                options = {opt: self.config.get(fxSection, opt) for opt in opts}

                fx = fxClasses[fx_type](layer, options)
                layer.effects.append(fx)

            if get("foreground", int, 0):
                self.foregroundLayers.append(layer)
            else:
                self.backgroundLayers.append(layer)

    def reset(self):
        self.lastBeatPos = None
        self.lastQuarterBeatPos = None
        self.lastMissPos = None
        self.lastPickPos = None
        self.beat = 0
        self.quarterBeat = 0
        self.pos = 0.0
        self.playedNotes = []
        self.averageNotes = [0.0]
        self.beatPeriod = 0.0

    def triggerPick(self, pos, notes):
        if notes:
            self.lastPickPos = pos
            self.playedNotes = self.playedNotes[-3:] + [sum(notes) / float(len(notes))]
            self.averageNotes[-1] = sum(self.playedNotes) / float(len(self.playedNotes))

    def triggerMiss(self, pos):
        self.lastMissPos = pos

    def triggerQuarterBeat(self, pos, quarterBeat):
        self.lastQuarterBeatPos = pos
        self.quarterBeat = quarterBeat

    def triggerBeat(self, pos, beat):
        self.lastBeatPos = pos
        self.beat = beat
        self.averageNotes = self.averageNotes[-4:] + self.averageNotes[-1:]

    def _renderLayers(self, layers, visibility):
        self.engine.view.setOrthogonalProjection(normalize=True)
        try:
            for layer in layers:
                layer.render(visibility)
        finally:
            self.engine.view.resetProjection()

    def run(self, pos, period):
        self.pos = pos
        self.beatPeriod = period
        quarterBeat = int(4 * pos / period)

        if quarterBeat > self.quarterBeat:
            self.triggerQuarterBeat(pos, quarterBeat)

        # Python 3: divisão inteira (em Py2 era int automaticamente)
        beat = quarterBeat // 4

        if beat > self.beat:
            self.triggerBeat(pos, beat)

    def render(self, visibility):
        self._renderLayers(self.backgroundLayers, visibility)
        self.scene.renderGuitar()
        self._renderLayers(self.foregroundLayers, visibility)
