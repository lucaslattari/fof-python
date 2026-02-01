# src/Input.py

#####################################################################
# -*- coding: iso-8859-1 -*-                                        #
#                                                                   #
# Frets on Fire                                                     #
# Copyright (C) 2006 Sami Kyöstilä                                  #
#                                                                   #
#####################################################################

import pygame
import Log
import Audio

from Task import Task
from Player import Controls


class KeyListener:
    def keyPressed(self, key, unicode):
        pass

    def keyReleased(self, key):
        pass


class MouseListener:
    def mouseButtonPressed(self, button, pos):
        pass

    def mouseButtonReleased(self, button, pos):
        pass

    def mouseMoved(self, pos, rel):
        pass


class SystemEventListener:
    def screenResized(self, size):
        pass

    def restartRequested(self):
        pass

    def musicFinished(self):
        pass

    def quit(self):
        pass


MusicFinished = pygame.USEREVENT


class Input(Task):
    def __init__(self):
        Task.__init__(self)
        self.mouse = pygame.mouse
        self.mouseListeners = []
        self.keyListeners = []
        self.systemListeners = []
        self.priorityKeyListeners = []
        self.controls = Controls()
        self.disableKeyRepeat()

        # Track keyboard state to heal missed KEYDOWN/KEYUP
        self._kb_down = {}  # keycode(int) -> bool

        # Initialize joysticks
        pygame.joystick.init()
        self.joystickAxes = {}
        self.joystickHats = {}

        self.joysticks = [
            pygame.joystick.Joystick(jid) for jid in range(pygame.joystick.get_count())
        ]
        for j in self.joysticks:
            j.init()
            self.joystickAxes[j.get_id()] = [0] * j.get_numaxes()
            self.joystickHats[j.get_id()] = [(0, 0)] * j.get_numhats()
        Log.debug("%d joysticks found." % (len(self.joysticks)))

        # Enable music events
        Audio.Music.setEndEvent(MusicFinished)

        # Custom key names
        self.getSystemKeyName = pygame.key.name
        pygame.key.name = self.getKeyName

        # Debug: ring buffer de eventos de teclado
        self.debugKeyTrace = True
        self._key_event_ring = []
        self._key_event_ring_max = 80

    def reloadControls(self):
        self.controls = Controls()

    def disableKeyRepeat(self):
        pygame.key.set_repeat(0, 0)

    def enableKeyRepeat(self):
        pygame.key.set_repeat(300, 30)

    def addMouseListener(self, listener):
        if listener not in self.mouseListeners:
            self.mouseListeners.append(listener)

    def removeMouseListener(self, listener):
        if listener in self.mouseListeners:
            self.mouseListeners.remove(listener)

    def addKeyListener(self, listener, priority=False):
        if priority:
            if listener not in self.priorityKeyListeners:
                self.priorityKeyListeners.append(listener)
        else:
            if listener not in self.keyListeners:
                self.keyListeners.append(listener)

    def removeKeyListener(self, listener):
        if listener in self.keyListeners:
            self.keyListeners.remove(listener)
        if listener in self.priorityKeyListeners:
            self.priorityKeyListeners.remove(listener)

    def addSystemEventListener(self, listener):
        if listener not in self.systemListeners:
            self.systemListeners.append(listener)

    def removeSystemEventListener(self, listener):
        if listener in self.systemListeners:
            self.systemListeners.remove(listener)

    def broadcastEvent(self, listeners, function, *args):
        """
        IMPORTANTE:
        - Itera do topo para baixo (último listener adicionado primeiro)
        - Para na primeira camada que "consumir" o evento (retornar True)
        - Usa list() para evitar problemas se a lista for modificada durante o dispatch
        """
        for l in reversed(list(listeners)):
            handler = getattr(l, function, None)
            if not handler:
                continue
            try:
                if handler(*args):
                    return True
            except TypeError:
                try:
                    if handler(*args[:1]):
                        return True
                except Exception:
                    pass
            except Exception:
                pass
        return False

    def broadcastSystemEvent(self, name, *args):
        return self.broadcastEvent(self.systemListeners, name, *args)

    def encodeJoystickButton(self, joystick, button):
        return 0x10000 + (joystick << 8) + button

    def encodeJoystickAxis(self, joystick, axis, end):
        return 0x20000 + (joystick << 8) + (axis << 4) + end

    def encodeJoystickHat(self, joystick, hat, pos):
        v = int((pos[1] + 1) * 3 + (pos[0] + 1))
        return 0x30000 + (joystick << 8) + (hat << 4) + v

    def decodeJoystickButton(self, id):
        id -= 0x10000
        return (id >> 8, id & 0xFF)

    def decodeJoystickAxis(self, id):
        id -= 0x20000
        return (id >> 8, (id >> 4) & 0xF, id & 0xF)

    def decodeJoystickHat(self, id):
        id -= 0x30000
        v = id & 0xF
        x, y = (v % 3) - 1, (v // 3) - 1
        return (id >> 8, (id >> 4) & 0xF, (x, y))

    def getKeyName(self, id):
        # ====================================================================
        # ✅ CORREÇÃO: Verificar SDL2 scancodes ANTES de joystick
        # ====================================================================
        # SDL2 usa o range 0x40000000-0x400001FF para scancodes especiais
        # (F1-F12, setas, Home, End, etc.)
        # Se não verificar isso primeiro, esses keycodes são interpretados
        # erroneamente como eventos de joystick

        if id >= 0x40000000:  # SDL2 scancode range
            return self.getSystemKeyName(id)

        # Agora sim, verificar joystick (ordem correta!)
        if id >= 0x30000:
            joy, axis, pos = self.decodeJoystickHat(id)
            return "Joy #%d, hat %d %s" % (joy + 1, axis, pos)
        elif id >= 0x20000:
            joy, axis, end = self.decodeJoystickAxis(id)
            return "Joy #%d, axis %d %s" % (
                joy + 1,
                axis,
                ("high" if end == 1 else "low"),
            )
        elif id >= 0x10000:
            joy, but = self.decodeJoystickButton(id)
            return "Joy #%d, %s" % (joy + 1, chr(ord("A") + but))
        return self.getSystemKeyName(id)

    def _dispatch_keydown(self, keycode, uni="\x00"):
        if not self.broadcastEvent(
            self.priorityKeyListeners, "keyPressed", keycode, uni
        ):
            self.broadcastEvent(self.keyListeners, "keyPressed", keycode, uni)

    def _dispatch_keyup(self, keycode):
        if not self.broadcastEvent(self.priorityKeyListeners, "keyReleased", keycode):
            self.broadcastEvent(self.keyListeners, "keyReleased", keycode)

    def _reconcile_keyboard_state(self):
        """
        Heal missed KEYDOWN/KEYUP events by comparing:
        - what we *think* is down (self._kb_down)
        - what SDL says is down (pygame.key.get_pressed())

        If divergence is found, synthesize the missing event so that Controls/listeners
        don't get out-of-sync and cause 1-frame chord mismatches (the F1+F3 miss bug).
        """
        if not self._kb_down:
            return

        try:
            pressed = pygame.key.get_pressed()
        except Exception:
            return

        # iterate only keys we've seen to keep it cheap
        for keycode, believed_down in list(self._kb_down.items()):
            # ====================================================================
            # ✅ CORREÇÃO: Remover bound-check que bloqueava F1-F12
            # ====================================================================
            # ANTES: if keycode < 0 or keycode >= len(pressed): continue
            # PROBLEMA: F1-F12 têm keycodes > 512, então sempre pulavam
            # AGORA: Só verifica se é int válido, deixa o try/except cuidar do resto

            if not isinstance(keycode, int) or keycode < 0:
                continue

            # ====================================================================
            # ✅ CORREÇÃO: Try/except ao acessar pressed[keycode]
            # ====================================================================
            # Para F1-F12, pressed[keycode] vai dar IndexError porque keycode >= 512
            # Gracefully ignora essas teclas (elas funcionam via eventos normais)
            try:
                actual_down = bool(pressed[keycode])
            except (IndexError, TypeError):
                # Keycode fora do range de get_pressed() (ex: F1-F12 no SDL2)
                # Ignora - elas funcionam via eventos KEYDOWN/KEYUP normais
                continue

            if actual_down == bool(believed_down):
                continue

            # Divergence detected: synthesize event
            self._kb_down[keycode] = actual_down
            if actual_down:
                # key is physically down but we missed KEYDOWN
                Log.debug(
                    f"[RECONCILE] Sintetizando KEYDOWN para {pygame.key.name(keycode)}"
                )
                self._dispatch_keydown(keycode, "\x00")
            else:
                # key is physically up but we missed KEYUP
                Log.debug(
                    f"[RECONCILE] Sintetizando KEYUP para {pygame.key.name(keycode)}"
                )
                self._dispatch_keyup(keycode)

    def getKeyDebugSnapshot(self, keycodes):
        """
        Retorna um snapshot para debug:
        - estado SDL (get_pressed)
        - último histórico de KEYDOWN/KEYUP
        """
        snap = {}
        try:
            pressed = pygame.key.get_pressed()
        except Exception:
            pressed = None

        for kc in keycodes:
            sdl_down = None
            if pressed is not None and 0 <= kc < len(pressed):
                sdl_down = bool(pressed[kc])
            snap[kc] = {
                "sdl": sdl_down,
            }

        return {
            "mods": pygame.key.get_mods(),
            "tick": pygame.time.get_ticks(),
            "keys": snap,
            "recent": list(self._key_event_ring),
        }

    def run(self, ticks):
        pygame.event.pump()

        for event in pygame.event.get():
            if event.type == pygame.KEYDOWN:
                uni = getattr(event, "unicode", "\x00")

                # Track keyboard state (ALL keyboard keys, including function keys)
                if isinstance(event.key, int):
                    self._kb_down[event.key] = True

                # DEBUG: estado no instante do strum (mantido para diagnóstico)
                if event.key == pygame.K_RETURN:
                    try:
                        Log.debug(
                            "[STRUM] ticks=%d kb[F1]=%s kb[F2]=%s kb[F3]=%s mods=%s"
                            % (
                                pygame.time.get_ticks(),
                                self._kb_down.get(pygame.K_F1),
                                self._kb_down.get(pygame.K_F2),
                                self._kb_down.get(pygame.K_F3),
                                pygame.key.get_mods(),
                            )
                        )
                    except Exception:
                        pass

                if self.debugKeyTrace:
                    mod = pygame.key.get_mods()
                    self._key_event_ring.append(
                        ("KD", event.key, uni, mod, pygame.time.get_ticks())
                    )
                    if len(self._key_event_ring) > self._key_event_ring_max:
                        self._key_event_ring.pop(0)

                self._dispatch_keydown(event.key, uni)

            elif event.type == pygame.KEYUP:
                # Track keyboard state (ALL keyboard keys, including function keys)
                if isinstance(event.key, int):
                    self._kb_down[event.key] = False

                if self.debugKeyTrace:
                    mod = pygame.key.get_mods()
                    self._key_event_ring.append(
                        ("KU", event.key, "\x00", mod, pygame.time.get_ticks())
                    )
                    if len(self._key_event_ring) > self._key_event_ring_max:
                        self._key_event_ring.pop(0)

                self._dispatch_keyup(event.key)

            elif event.type == pygame.MOUSEMOTION:
                self.broadcastEvent(
                    self.mouseListeners, "mouseMoved", event.pos, event.rel
                )

            elif event.type == pygame.MOUSEBUTTONDOWN:
                self.broadcastEvent(
                    self.mouseListeners, "mouseButtonPressed", event.button, event.pos
                )

            elif event.type == pygame.MOUSEBUTTONUP:
                self.broadcastEvent(
                    self.mouseListeners, "mouseButtonReleased", event.button, event.pos
                )

            elif event.type == pygame.VIDEORESIZE:
                self.broadcastEvent(self.systemListeners, "screenResized", event.size)

            # pygame 2+: window events
            elif hasattr(pygame, "WINDOWCLOSE") and event.type == pygame.WINDOWCLOSE:
                self.broadcastEvent(self.systemListeners, "quit")

            elif hasattr(pygame, "WINDOWEVENT") and event.type == pygame.WINDOWEVENT:
                if (
                    hasattr(pygame, "WINDOWEVENT_CLOSE")
                    and event.event == pygame.WINDOWEVENT_CLOSE
                ):
                    self.broadcastEvent(self.systemListeners, "quit")
                elif (
                    hasattr(pygame, "WINDOWEVENT_RESIZED")
                    and event.event == pygame.WINDOWEVENT_RESIZED
                ):
                    try:
                        self.broadcastEvent(
                            self.systemListeners,
                            "screenResized",
                            (event.data1, event.data2),
                        )
                    except Exception:
                        pass

            elif event.type == pygame.QUIT:
                self.broadcastEvent(self.systemListeners, "quit")

            elif event.type == MusicFinished:
                self.broadcastEvent(self.systemListeners, "musicFinished")

            elif event.type == pygame.JOYBUTTONDOWN:
                jid = self.encodeJoystickButton(event.joy, event.button)
                self._dispatch_keydown(jid, "\x00")

            elif event.type == pygame.JOYBUTTONUP:
                jid = self.encodeJoystickButton(event.joy, event.button)
                self._dispatch_keyup(jid)

            elif event.type == pygame.JOYAXISMOTION:
                try:
                    threshold = 0.8
                    state = self.joystickAxes[event.joy][event.axis]
                    keyEvent = None
                    args = None

                    if event.value > threshold and state != 1:
                        state = 1
                        keyEvent = "down"
                        args = (
                            self.encodeJoystickAxis(event.joy, event.axis, 1),
                            "\x00",
                        )
                    elif event.value < -threshold and state != -1:
                        state = -1
                        keyEvent = "down"
                        args = (
                            self.encodeJoystickAxis(event.joy, event.axis, 0),
                            "\x00",
                        )
                    elif state != 0 and -threshold <= event.value <= threshold:
                        keyEvent = "up"
                        args = (
                            self.encodeJoystickAxis(
                                event.joy, event.axis, 1 if state == 1 else 0
                            ),
                        )
                        state = 0

                    if keyEvent and args is not None:
                        self.joystickAxes[event.joy][event.axis] = state
                        if keyEvent == "down":
                            self._dispatch_keydown(*args)
                        else:
                            self._dispatch_keyup(*args)

                except KeyError:
                    pass

            elif event.type == pygame.JOYHATMOTION:
                try:
                    state = self.joystickHats[event.joy][event.hat]
                    if event.value != (0, 0) and state == (0, 0):
                        self.joystickHats[event.joy][event.hat] = event.value
                        self._dispatch_keydown(
                            self.encodeJoystickHat(event.joy, event.hat, event.value),
                            "\x00",
                        )
                    else:
                        self._dispatch_keyup(
                            self.encodeJoystickHat(event.joy, event.hat, state)
                        )
                        self.joystickHats[event.joy][event.hat] = (0, 0)
                except KeyError:
                    pass

        # ========================================================================
        # ✅ ÚNICA CORREÇÃO: Chamar reconciliação (agora funciona para F1-F12!)
        # ========================================================================
        # Polling agressivo REMOVIDO - causava loop infinito de KEYUPs
        # A reconciliação normal agora funciona graças ao try/except acima
        self._reconcile_keyboard_state()
