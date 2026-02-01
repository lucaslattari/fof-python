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
#####################################################################

import pygame
from OpenGL.GL import *
import math

from View import Layer
from Input import KeyListener
import Data
import Theme
import Dialogs
import Player


class Choice:
    def __init__(self, text, callback, values=None, valueIndex=0):
        # Py3: não existe unicode(). Queremos sempre str.
        self.text = str(text)
        self.callback = callback
        self.values = values
        self.valueIndex = valueIndex

        if self.text.endswith(" >"):
            self.text = self.text[:-2]
            self.isSubMenu = True
        else:
            self.isSubMenu = isinstance(self.callback, Menu) or isinstance(
                self.callback, list
            )

    def trigger(self, engine=None):
        if engine and isinstance(self.callback, list):
            nextMenu = Menu(engine, self.callback)
        elif engine and isinstance(self.callback, Menu):
            nextMenu = self.callback
        elif self.values:
            nextMenu = self.callback(self.values[self.valueIndex])
        else:
            nextMenu = self.callback()

        if isinstance(nextMenu, Menu):
            engine.view.pushLayer(nextMenu)

    def selectNextValue(self):
        if self.values:
            self.valueIndex = (self.valueIndex + 1) % len(self.values)
            self.trigger()

    def selectPreviousValue(self):
        if self.values:
            self.valueIndex = (self.valueIndex - 1) % len(self.values)
            self.trigger()

    def getText(self, selected):
        if not self.values:
            if self.isSubMenu:
                return "%s >" % self.text
            return self.text
        if selected:
            return "%s: %s%s%s" % (
                self.text,
                Data.LEFT,
                self.values[self.valueIndex],
                Data.RIGHT,
            )
        else:
            return "%s: %s" % (self.text, self.values[self.valueIndex])


class Menu(Layer, KeyListener):
    def __init__(
        self,
        engine,
        choices,
        onClose=None,
        onCancel=None,
        pos=(0.2, 0.66 - 0.35),
        viewSize=6,
        fadeScreen=False,
    ):
        self.engine = engine
        self.choices = []
        self.currentIndex = 0
        self.time = 0
        self.onClose = onClose
        self.onCancel = onCancel
        self.viewOffset = 0
        self.pos = pos
        self.viewSize = viewSize
        self.fadeScreen = fadeScreen

        # Debounce de CANCEL dentro do Menu: pygame + key repeat pode gerar spam.
        self._lastCancelMs = -10_000
        self._cancelDebounceMs = 200

        for c in choices:
            try:
                text, callback = c
                if isinstance(text, tuple):
                    c = Choice(text[0], callback, values=text[2], valueIndex=text[1])
                else:
                    c = Choice(text, callback)
            except TypeError:
                # Se já for um Choice ou algo compatível, cai aqui e só adiciona.
                pass
            self.choices.append(c)

    def selectItem(self, index):
        self.currentIndex = index

    def shown(self):
        self.engine.input.addKeyListener(self)
        # Nota: enableKeyRepeat amplifica o problema do ESC; mas vamos manter (compat),
        # e mitigar com debounce.
        self.engine.input.enableKeyRepeat()

    def hidden(self):
        # hidden() é o "lugar certo" de soltar key listener/repeat.
        self.engine.input.removeKeyListener(self)
        self.engine.input.disableKeyRepeat()
        if self.onClose:
            self.onClose()

    def updateSelection(self):
        if self.currentIndex > self.viewOffset + self.viewSize - 1:
            self.viewOffset = self.currentIndex - self.viewSize + 1
        if self.currentIndex < self.viewOffset:
            self.viewOffset = self.currentIndex

    def keyPressed(self, key, unicode=""):
        self.time = 0
        choice = self.choices[self.currentIndex]
        c = self.engine.input.controls.getMapping(key)

        if c in [Player.KEY1] or key == pygame.K_RETURN:
            choice.trigger(self.engine)
            self.engine.data.acceptSound.play()

        elif c in [Player.CANCEL, Player.KEY2]:
            # Debounce: evita ESC repetido fechar menu e "vazar" pro layer de baixo.
            now_ms = pygame.time.get_ticks()
            if now_ms - self._lastCancelMs < self._cancelDebounceMs:
                return True
            self._lastCancelMs = now_ms

            if self.onCancel:
                self.onCancel()

            # IMPORTANTE: remova listener/repeat agora para não processar mais eventos
            # durante a transição do View.
            self.engine.input.removeKeyListener(self)
            self.engine.input.disableKeyRepeat()

            self.engine.data.cancelSound.play()
            self.engine.view.popLayer(self)

        elif c in [Player.DOWN, Player.ACTION2]:
            self.currentIndex = (self.currentIndex + 1) % len(self.choices)
            self.updateSelection()
            self.engine.data.selectSound.play()

        elif c in [Player.UP, Player.ACTION1]:
            self.currentIndex = (self.currentIndex - 1) % len(self.choices)
            self.updateSelection()
            self.engine.data.selectSound.play()

        elif c in [Player.RIGHT, Player.KEY4]:
            choice.selectNextValue()

        elif c in [Player.LEFT, Player.KEY3]:
            choice.selectPreviousValue()

        return True

    def run(self, ticks):
        self.time += ticks / 50.0

    def renderTriangle(self, up=(0, 1), s=0.2):
        left = (-up[1], up[0])
        glBegin(GL_TRIANGLES)
        glVertex2f(up[0] * s, up[1] * s)
        glVertex2f((-up[0] + left[0]) * s, (-up[1] + left[1]) * s)
        glVertex2f((-up[0] - left[0]) * s, (-up[1] - left[1]) * s)
        glEnd()

    def render(self, visibility, topMost):
        if not visibility:
            return

        self.engine.view.setOrthogonalProjection(normalize=True)
        try:
            v = (1 - visibility) ** 2
            font = self.engine.data.font

            if self.fadeScreen:
                Dialogs.fadeScreen(v)

            glEnable(GL_BLEND)
            glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
            glEnable(GL_COLOR_MATERIAL)

            n = len(self.choices)
            x, y = self.pos
            w, h = font.getStringSize("_")

            for i, choice in enumerate(
                self.choices[self.viewOffset : self.viewOffset + self.viewSize]
            ):
                text = choice.getText(i + self.viewOffset == self.currentIndex)
                glPushMatrix()
                glRotate(v * 45, 0, 0, 1)

                # Draw arrows if scrolling is needed to see all items
                if i == 0 and self.viewOffset > 0:
                    Theme.setBaseColor(
                        (1 - v) * max(0.1, 1 - (1.0 / self.viewOffset) / 3)
                    )
                    glPushMatrix()
                    glTranslatef(x - v / 4 - w * 2, y + h / 2, 0)
                    self.renderTriangle(up=(0, -1), s=0.015)
                    glPopMatrix()
                elif i == self.viewSize - 1 and self.viewOffset + self.viewSize < n:
                    Theme.setBaseColor(
                        (1 - v)
                        * max(
                            0.1, 1 - (1.0 / (n - self.viewOffset - self.viewSize)) / 3
                        )
                    )
                    glPushMatrix()
                    glTranslatef(x - v / 4 - w * 2, y + h / 2, 0)
                    self.renderTriangle(up=(0, 1), s=0.015)
                    glPopMatrix()

                if i + self.viewOffset == self.currentIndex:
                    a = (math.sin(self.time) * 0.15 + 0.75) * (1 - v * 2)
                    Theme.setSelectedColor(a)
                    a *= -0.005
                    glTranslatef(a, a, a)
                else:
                    Theme.setBaseColor(1 - v)

                font.render(text, (x - v / 4, y))
                v *= 2
                y += h
                glPopMatrix()
        finally:
            self.engine.view.resetProjection()
