# src/GuitarScene.py
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

from Scene import SceneServer, SceneClient
from Song import Note, TextEvent, PictureEvent, loadSong
from Menu import Menu
from Guitar import Guitar, KEYS
from Language import _
import Player
import Dialogs
import Data
import Theme
import View
import Audio
import Stage
import Settings

import math
import pygame
import random
import os
import Log
from OpenGL.GL import *


class GuitarScene:
    pass


class GuitarSceneServer(GuitarScene, SceneServer):
    pass


class GuitarSceneClient(GuitarScene, SceneClient):
    def createClient(self, libraryName, songName):
        self.songStarted = False
        self.paused = False
        self.guitar = Guitar(self.engine)
        self.visibility = 0.0
        self.libraryName = libraryName
        self.songName = songName
        self.done = False
        self.sfxChannel = self.engine.audio.getChannel(
            self.engine.audio.getChannelCount() - 1
        )
        self.lastMultTime = None
        self.cheatCodes = [
            (
                [117, 112, 116, 111, 109, 121, 116, 101, 109, 112, 111],
                self.toggleAutoPlay,
            ),
            ([102, 97, 115, 116, 102, 111, 114, 119, 97, 114, 100], self.goToResults),
        ]
        self.enteredCode = []
        self.song = None
        self.autoPlay = False
        self.lastPickPos = None
        self.lastSongPos = 0.0
        self.keyBurstTimeout = None
        self.keyBurstPeriod = 30
        self.camera.target = (0, 0, 4)
        self.camera.origin = (0, 3, -3)

        # --- ESC / cancel debounce (pygame moderno tende a repetir keydown) ---
        self._lastCancelMs = -10_000
        self._cancelDebounceMs = 200  # bem conservador: evita "spam" de ESC

        self.loadSettings()
        self.engine.resource.load(
            self,
            "song",
            lambda: loadSong(self.engine, songName, library=libraryName),
            onLoad=self.songLoaded,
        )

        self.stage = Stage.Stage(self, self.engine.resource.fileName("stage.ini"))

        self.engine.loadSvgDrawing(self, "fx2x", "2x.svg", textureSize=(256, 256))
        self.engine.loadSvgDrawing(self, "fx3x", "3x.svg", textureSize=(256, 256))
        self.engine.loadSvgDrawing(self, "fx4x", "4x.svg", textureSize=(256, 256))

        Dialogs.showLoadingScreen(
            self.engine, lambda: self.song, text=_("Tuning Guitar...")
        )

        settingsMenu = Settings.GameSettingsMenu(self.engine)
        settingsMenu.fadeScreen = True

        self.menu = Menu(
            self.engine,
            [
                (_("Return to Song"), lambda: None),
                (_("Restart Song"), self.restartSong),
                (_("Change Song"), self.changeSong),
                (_("Settings"), settingsMenu),
                (_("Quit to Main Menu"), self.quit),
            ],
            fadeScreen=True,
            onClose=self.resumeGame,
        )

        self.restartSong()

        # ========================================================================
        # ✅ CORREÇÃO CRÍTICA: Unificar as instâncias de Controls
        # ========================================================================
        # Bug: GuitarScene herda self.controls de SceneClient, mas self.player
        # tem sua própria instância (self.player.controls). Isso causa dessincronia
        # porque eventos vão para uma instância e validação consulta outra.
        #
        # Solução: Fazer ambas apontarem para o mesmo objeto
        import Log

        Log.warn("=" * 60)
        Log.warn("UNIFICANDO INSTÂNCIAS DE CONTROLS")
        Log.warn("=" * 60)
        Log.warn(f"ANTES: self.controls ID = {id(self.controls)}")
        Log.warn(f"ANTES: self.player.controls ID = {id(self.player.controls)}")

        # Faz self.controls apontar para a mesma instância do player
        self.controls = self.player.controls

        Log.warn(f"DEPOIS: self.controls ID = {id(self.controls)}")
        Log.warn(f"DEPOIS: self.player.controls ID = {id(self.player.controls)}")
        Log.warn(f"Same? {id(self.controls) == id(self.player.controls)}")
        Log.warn("=" * 60)
        # ========================================================================

    # --------------------
    # Pause / Resume
    # --------------------
    def pauseGame(self):
        # Pausa "de verdade" em qualquer fase (inclusive countdown)
        if getattr(self, "paused", False):
            return
        self.paused = True

        # Se a música já estava tocando, pausa ela
        if self.song and self.song.isPlaying():
            self.song.pause()

    def resumeGame(self):
        self.loadSettings()

        # Retoma apenas se estava pausado
        if not getattr(self, "paused", False):
            return
        self.paused = False

        # Se existe música, tenta despausar (se não estiver tocando ainda, ok)
        if self.song:
            try:
                self.song.unpause()
            except Exception:
                # some implementações não gostam de unpause antes de play
                pass

    # --------------------
    # Settings
    # --------------------
    def loadSettings(self):
        self.delay = self.engine.config.get("audio", "delay")
        self.screwUpVolume = self.engine.config.get("audio", "screwupvol")
        self.guitarVolume = self.engine.config.get("audio", "guitarvol")
        self.songVolume = self.engine.config.get("audio", "songvol")
        self.rhythmVolume = self.engine.config.get("audio", "rhythmvol")
        self.guitar.leftyMode = self.engine.config.get("game", "leftymode")

        if self.song:
            self.song.setBackgroundVolume(self.songVolume)
            self.song.setRhythmVolume(self.rhythmVolume)

    def songLoaded(self, song):
        song.difficulty = self.player.difficulty
        self.delay += song.info.delay

        # If tapping is disabled, remove the tapping indicators
        if not self.engine.config.get("game", "tapping"):
            for time, event in self.song.track.getAllEvents():
                if isinstance(event, Note):
                    event.tappable = False

    # --------------------
    # Flow actions
    # --------------------
    def quit(self):
        if self.song:
            self.song.stop()
            self.song = None
        self.done = True
        self.engine.view.popLayer(self.menu)
        self.session.world.finishGame()

    def changeSong(self):
        if self.song:
            self.song.stop()
            self.song = None
        self.engine.view.popLayer(self.menu)
        self.session.world.deleteScene(self)
        self.session.world.createScene("SongChoosingScene")

    def restartSong(self):
        self.songStarted = False
        self.paused = False
        self.engine.data.startSound.play()
        self.engine.view.popLayer(self.menu)
        self.player.reset()
        self.stage.reset()
        self.enteredCode = []
        self.autoPlay = False
        self.engine.collectGarbage()

        if not self.song:
            return

        self.countdown = 8.0
        self.guitar.endPick(0)
        self.song.stop()

    # --------------------
    # Main loop
    # --------------------
    def run(self, ticks):
        SceneClient.run(self, ticks)

        # Se pausado, congela o tempo da cena (inclui countdown)
        if getattr(self, "paused", False):
            return

        pos = self.getSongPosition()

        # update song
        if self.song:
            # update stage
            self.stage.run(pos, self.guitar.currentPeriod)

            if (
                self.songStarted
                and not self.song.isPlaying()
                and not self.done
                and not self.paused
            ):
                self.goToResults()
                return

            if self.autoPlay:
                notes = self.guitar.getRequiredNotes(self.song, pos)
                notes = [note.number for time, note in notes]

                changed = False
                held = 0
                for n, k in enumerate(KEYS):
                    if n in notes and not self.controls.getState(k):
                        changed = True
                        self.controls.toggle(k, True)
                    elif n not in notes and self.controls.getState(k):
                        changed = True
                        self.controls.toggle(k, False)
                    if self.controls.getState(k):
                        held += 1
                if changed and held:
                    self.doPick()

            self.song.update(ticks)
            if self.countdown > 0:
                self.guitar.setBPM(self.song.bpm)
                self.countdown = max(self.countdown - ticks / self.song.period, 0)
                if not self.countdown:
                    self.engine.collectGarbage()
                    self.song.setGuitarVolume(self.guitarVolume)
                    self.song.setBackgroundVolume(self.songVolume)
                    self.song.setRhythmVolume(self.rhythmVolume)
                    if not getattr(self, "paused", False):
                        self.song.play()
                        self.songStarted = True

        # update board
        if not self.guitar.run(ticks, pos, self.controls):
            # done playing the current notes
            self.endPick()

        # missed some notes?
        if (
            self.song
            and self.guitar.getMissedNotes(self.song, pos)
            and not self.guitar.playedNotes
        ):
            try:
                # --- SANITY: dump no momento do miss ---
                required = self.guitar.getRequiredNotes(self.song, pos)
                required_nums = [note.number for time, note in required]
                required_times = [float(time) for time, note in required]
                last_strum = getattr(self, "_last_strum", None)

                # KEYS = lista dos frets do gameplay
                held_keys = []
                pressed_frets = []
                for n, k in enumerate(KEYS):
                    if self.controls.getState(k):
                        held_keys.append((n, k))
                        pressed_frets.append(n)

                lowest = min(pressed_frets) if pressed_frets else None
                highest = max(pressed_frets) if pressed_frets else None

                # --- detectar "strum/pick" (ajuste aqui conforme teu projeto) ---
                # Tenta algumas convenções comuns sem quebrar se não existir.
                strum_states = {}
                for name in ("PICK", "STRUM_UP", "STRUM_DOWN", "ACTION1", "ACTION2"):
                    key = globals().get(name, None)
                    if key is not None:
                        try:
                            strum_states[name] = bool(self.controls.getState(key))
                        except Exception:
                            strum_states[name] = "ERR"
                    else:
                        strum_states[name] = None

                # --- nota mais próxima (mesmo quando req=[]) ---
                # Heurística: varre um pequeno range ao redor e pega o evento mais próximo.
                nearest = None  # (dt, note_num, note_time)
                try:
                    window = 200.0  # ms (ajustável)
                    # varremos em passos pequenos para não depender de internals
                    # (se você tiver um método "getNotesInRange", melhor ainda)
                    candidates = []
                    for t in (
                        pos - window,
                        pos - 100.0,
                        pos - 50.0,
                        pos,
                        pos + 50.0,
                        pos + 100.0,
                        pos + window,
                    ):
                        cand = self.guitar.getRequiredNotes(self.song, t)
                        for note_time, note in cand:
                            candidates.append((float(note_time), int(note.number)))

                    # remove duplicatas
                    uniq = {}
                    for nt, nn in candidates:
                        uniq[(nt, nn)] = True

                    for nt, nn in uniq.keys():
                        dt = float(pos) - float(nt)
                        if (nearest is None) or (abs(dt) < abs(nearest[0])):
                            nearest = (dt, nn, nt)
                except Exception:
                    nearest = "ERR"

                # --- Debug key snapshot: F1/F3 + frets ---
                debug_keycodes = [pygame.K_F1, pygame.K_F3, pygame.K_RETURN]
                for _, k in held_keys:
                    if isinstance(k, int) and k < 0x10000:
                        debug_keycodes.append(k)
                debug_keycodes = sorted(set(debug_keycodes))

                snap = None
                if hasattr(self.engine, "input") and hasattr(
                    self.engine.input, "getKeyDebugSnapshot"
                ):
                    snap = self.engine.input.getKeyDebugSnapshot(debug_keycodes)

                # Render amigável dos frets
                held_pretty = []
                if hasattr(self.engine, "input"):
                    for n, k in held_keys:
                        try:
                            held_pretty.append((n, self.engine.input.getKeyName(k)))
                        except Exception:
                            held_pretty.append((n, k))
                else:
                    held_pretty = held_keys

                recent_tail = None
                if snap and isinstance(snap, dict) and snap.get("recent"):
                    try:
                        recent_tail = snap["recent"][-14:]
                    except Exception:
                        recent_tail = snap.get("recent")

                Log.warn(
                    "[SANITY][MISS] pos=%.3f req=%s req_t=%s pressed=%s lowest=%s highest=%s strum=%s mods=%s keys=%s recent_tail=%s nearest=%s"
                    % (
                        float(pos),
                        required_nums,
                        required_times,
                        pressed_frets,
                        lowest,
                        highest,
                        strum_states,
                        snap.get("mods") if snap else None,
                        (snap.get("keys") if snap else None),
                        recent_tail,
                        nearest,
                    )
                )
            except Exception as e:
                Log.warn("[SANITY][MISS] debug failed: %s" % e)

            self.song.setGuitarVolume(0.0)
            self.player.streak = 0

        # late pick
        if (
            self.keyBurstTimeout is not None
            and self.engine.timer.time > self.keyBurstTimeout
        ):
            self.keyBurstTimeout = None
            notes = self.guitar.getRequiredNotes(self.song, pos)
            if self.guitar.controlsMatchNotes(self.controls, notes):
                self.doPick()

    def endPick(self):
        score = self.getExtraScoreForCurrentlyPlayedNotes()
        if not self.guitar.endPick(self.song.getPosition()):
            self.song.setGuitarVolume(0.0)
        self.player.addScore(score)

    def render3D(self):
        self.stage.render(self.visibility)

    def renderGuitar(self):
        self.guitar.render(
            self.visibility, self.song, self.getSongPosition(), self.controls
        )

    def getSongPosition(self):
        if self.song:
            if not self.done:
                try:
                    self.lastSongPos = self.song.getPosition()
                except pygame.error:
                    # mixer morreu durante shutdown
                    return getattr(self, "lastSongPos", 0.0) - self.delay

                return self.lastSongPos - self.countdown * self.song.period - self.delay
            else:
                return (
                    self.lastSongPos
                    + 4.0 * (1 - self.visibility) * self.song.period
                    - self.delay
                )
        return 0.0

    def doPick(self):
        if not self.song:
            return

        pos = self.getSongPosition()

        # ====================================================================
        # 🔍 DIAGNÓSTICO DE TIMING
        # ====================================================================
        import Log

        notes = self.guitar.getRequiredNotes(self.song, pos)

        if notes:
            note_times = [time for time, event in notes]
            note_numbers = [event.number for time, event in notes]
            Log.warn(
                f"[TIMING] pos={pos:.3f} | notas={note_numbers} em times={note_times}"
            )
        else:
            # Buscar nota mais próxima
            track = self.song.track
            all_notes = [
                (time, event)
                for time, event in track.getEvents(pos - 1000, pos + 1000)
                if isinstance(event, Note)
            ]

            if all_notes:
                closest = min(all_notes, key=lambda x: abs(x[0] - pos))
                diff = pos - closest[0]
                Log.error(
                    f"[TIMING] MISS! pos={pos:.3f} | nota_proxima={closest[1].number} em {closest[0]:.3f} | diff={diff:.3f}ms | lateMargin={self.guitar.lateMargin:.3f} earlyMargin={self.guitar.earlyMargin:.3f}"
                )
        # ====================================================================

        if self.guitar.playedNotes:
            if (
                self.guitar.areNotesTappable(self.guitar.playedNotes)
                and not self.guitar.getRequiredNotes(self.song, pos)
                and self.lastPickPos is not None
                and pos - self.lastPickPos <= self.song.period / 2
            ):
                return
            self.endPick()

        self.lastPickPos = pos

        # ====================================================================
        # ✅ CORREÇÃO: Implementação SIMPLIFICADA do snapshot
        # ====================================================================
        import Log

        # Usar snapshot se disponível, caso contrário usar controls diretamente
        use_snapshot = (
            hasattr(self, "_controls_snapshot") and self._controls_snapshot is not None
        )

        if use_snapshot:
            # Criar classe simples para wrappear o snapshot
            class SnapshotControls:
                def __init__(self, snapshot):
                    self._snapshot = snapshot

                def getState(self, key):
                    return self._snapshot.get(key, False)

            controls_to_use = SnapshotControls(self._controls_snapshot)
            Log.debug(
                f"[DOPICK] Usando SNAPSHOT: {[n for n in range(5) if self._controls_snapshot.get(KEYS[n])]}"
            )
        else:
            controls_to_use = self.controls
            Log.debug(f"[DOPICK] Usando controles DIRETOS")

        # ====================================================================

        if self.guitar.startPick(self.song, pos, controls_to_use):
            # Limpar snapshot APÓS uso bem-sucedido
            if use_snapshot:
                self._controls_snapshot = None

            self.song.setGuitarVolume(self.guitarVolume)
            self.player.streak += 1
            self.player.notesHit += len(self.guitar.playedNotes)
            self.player.addScore(len(self.guitar.playedNotes) * 50)
            self.stage.triggerPick(pos, [n[1].number for n in self.guitar.playedNotes])
            if self.player.streak % 10 == 0:
                self.lastMultTime = pos
        else:
            # Limpar snapshot mesmo em caso de falha
            if use_snapshot:
                self._controls_snapshot = None

            self.song.setGuitarVolume(0.0)
            self.player.streak = 0
            self.stage.triggerMiss(pos)
            self.sfxChannel.play(self.engine.data.screwUpSound)
            self.sfxChannel.setVolume(self.screwUpVolume)

    def toggleAutoPlay(self):
        self.autoPlay = not self.autoPlay
        if self.autoPlay:
            Dialogs.showMessage(self.engine, _("Jurgen will show you how it is done."))
        else:
            Dialogs.showMessage(self.engine, _("Jurgen has left the building."))
        return self.autoPlay

    def goToResults(self):
        if self.song:
            self.song.stop()
            self.song = None
            self.done = True
            self.session.world.deleteScene(self)
            self.session.world.createScene(
                "GameResultsScene", libraryName=self.libraryName, songName=self.songName
            )

    # --------------------
    # Input
    # --------------------
    def _menuIsOnTop(self):
        # Evita depender de APIs novas do View: usa a lista de layers se existir
        v = getattr(self.engine, "view", None)
        if not v:
            return False
        layers = getattr(v, "layers", None)
        if not layers:
            return False
        return layers and layers[-1] is self.menu

    def _pushPauseMenuIfNeeded(self):
        # Não empilha pause menu duas vezes
        if self._menuIsOnTop():
            return
        self.pauseGame()
        self.engine.view.pushLayer(self.menu)

    def keyPressed(self, key, unicode=""):
        # ========================================================================
        # 🔍 DEBUG (remover depois)
        # ========================================================================
        import Log

        key_name = pygame.key.name(key) if isinstance(key, int) else str(key)
        controls_id = id(self.controls)
        player_controls_id = (
            id(self.player.controls) if hasattr(self, "player") else None
        )

        state_before = {}
        for n, k in enumerate(KEYS):
            state_before[n] = self.controls.getState(k)

        Log.debug(
            f"[SCENE] KEYDOWN {key_name} | controls_id={controls_id} player_id={player_controls_id} same={controls_id == player_controls_id}"
        )
        # ========================================================================

        control = self.controls.keyPressed(key)

        # ========================================================================
        # ✅ CORREÇÃO CRÍTICA: Snapshot do estado ANTES de processar outros eventos
        # ========================================================================
        # Bug: pygame processa múltiplos eventos por frame. Se o usuário pressiona
        # F2+F3 e dá STRUM, mas depois solta F2 e pressiona F1 ANTES do próximo
        # frame, quando doPick() executa, vê F1+F3 ao invés de F2+F3!
        #
        # Solução: Capturar o estado dos controles IMEDIATAMENTE quando
        # ACTION1/ACTION2 são pressionados, antes de processar próximos eventos.

        if control in (Player.ACTION1, Player.ACTION2):
            # Captura snapshot dos controles AGORA
            self._controls_snapshot = {}
            for n, k in enumerate(KEYS):
                self._controls_snapshot[k] = self.controls.getState(k)

            Log.debug(
                f"[SNAPSHOT] Capturado no STRUM: {[n for n in range(5) if self._controls_snapshot.get(KEYS[n])]}"
            )
        # ========================================================================

        # ========================================================================
        # 🔍 DEBUG (remover depois)
        # ========================================================================
        state_after = {}
        for n, k in enumerate(KEYS):
            state_after[n] = self.controls.getState(k)

        changed = {
            n: (state_before[n], state_after[n])
            for n in range(5)
            if state_before[n] != state_after[n]
        }
        if changed:
            Log.debug(f"[SCENE] KEYDOWN {key_name} changed controls: {changed}")
        # ========================================================================

        if control in (Player.ACTION1, Player.ACTION2):
            for k in KEYS:
                if self.controls.getState(k):
                    self.keyBurstTimeout = None
                    break
            else:
                self.keyBurstTimeout = self.engine.timer.time + self.keyBurstPeriod
                return True

        if control in (Player.ACTION1, Player.ACTION2) and self.song:
            self.doPick()
        elif control in KEYS and self.song:
            # Check whether we can tap the currently required notes
            pos = self.getSongPosition()
            notes = self.guitar.getRequiredNotes(self.song, pos)

            if (
                self.player.streak > 0
                and self.guitar.areNotesTappable(notes)
                and self.guitar.controlsMatchNotes(self.controls, notes)
            ):
                self.doPick()
        elif control == Player.CANCEL:
            # --- ESC fix: debounce + não sair da cena por "spam" de cancel ---
            now_ms = pygame.time.get_ticks()
            if now_ms - self._lastCancelMs < self._cancelDebounceMs:
                return True
            self._lastCancelMs = now_ms

            # Se já acabou/sem música, não faz nada perigoso
            if self.done or not self.song:
                return True

            # Abre pause menu (sem empilhar duplicado)
            self._pushPauseMenuIfNeeded()
            return True
        elif key >= ord("a") and key <= ord("z"):
            # cheat codes
            n = len(self.enteredCode)
            for code, func in self.cheatCodes:
                if n < len(code):
                    if key == code[n]:
                        self.enteredCode.append(key)
                        if self.enteredCode == code:
                            self.enteredCode = []
                            self.player.cheating = True
                            func()
                        break
            else:
                self.enteredCode = []

    def getExtraScoreForCurrentlyPlayedNotes(self):
        if not self.song:
            return 0

        noteCount = len(self.guitar.playedNotes)
        pickLength = self.guitar.getPickLength(self.getSongPosition())
        if pickLength > 1.1 * self.song.period / 4:
            return int(0.1 * pickLength * noteCount)
        return 0

    def keyReleased(self, key):
        # ========================================================================
        # 🔍 DEBUG: Verificar estado ANTES e DEPOIS
        # ========================================================================
        import Log

        key_name = pygame.key.name(key) if isinstance(key, int) else str(key)

        # Estado ANTES
        state_before = {}
        for n, k in enumerate(KEYS):
            state_before[n] = self.controls.getState(k)

        # ========================================================================

        result = self.controls.keyReleased(key)

        # ========================================================================
        # 🔍 DEBUG: Estado DEPOIS
        # ========================================================================
        state_after = {}
        for n, k in enumerate(KEYS):
            state_after[n] = self.controls.getState(k)

        # Ver o que mudou
        changed = {
            n: (state_before[n], state_after[n])
            for n in range(5)
            if state_before[n] != state_after[n]
        }
        if changed:
            Log.debug(f"[SCENE] KEYUP {key_name} changed controls: {changed}")
        # ========================================================================

        if result in KEYS and self.song:
            # Check whether we can tap the currently required notes
            pos = self.getSongPosition()
            notes = self.guitar.getRequiredNotes(self.song, pos)
            if (
                self.player.streak > 0
                and self.guitar.areNotesTappable(notes)
                and self.guitar.controlsMatchNotes(self.controls, notes)
            ):
                self.doPick()
            # Otherwise we end the pick if the notes have been playing long enough
            elif (
                self.lastPickPos is not None
                and pos - self.lastPickPos > self.song.period / 2
            ):
                self.endPick()

    # --------------------
    # Render
    # --------------------
    def render(self, visibility, topMost):
        SceneClient.render(self, visibility, topMost)

        font = self.engine.data.font
        bigFont = self.engine.data.bigFont

        self.visibility = v = 1.0 - ((1 - visibility) ** 2)

        self.engine.view.setOrthogonalProjection(normalize=True)
        try:
            # show countdown
            if self.countdown > 1:
                Theme.setBaseColor(min(1.0, 3.0 - abs(4.0 - self.countdown)))
                text = _("Get Ready to Rock")
                w, h = font.getStringSize(text)
                font.render(text, (0.5 - w / 2, 0.3))
                if self.countdown < 6:
                    scale = 0.002 + 0.0005 * (self.countdown % 1) ** 3
                    text = "%d" % (self.countdown)
                    w, h = bigFont.getStringSize(text, scale=scale)
                    Theme.setSelectedColor()
                    bigFont.render(text, (0.5 - w / 2, 0.45 - h / 2), scale=scale)

            w, h = font.getStringSize(" ")
            y = 0.05 - h / 2 - (1.0 - v) * 0.2

            # show song name
            if self.countdown and self.song:
                Theme.setBaseColor(min(1.0, 4.0 - abs(4.0 - self.countdown)))
                Dialogs.wrapText(
                    font,
                    (0.05, 0.05 - h / 2),
                    self.song.info.name + " \n " + self.song.info.artist,
                    rightMargin=0.6,
                    scale=0.0015,
                )

            Theme.setSelectedColor()

            font.render(
                "%d"
                % (self.player.score + self.getExtraScoreForCurrentlyPlayedNotes()),
                (0.6, y),
            )
            font.render("%dx" % self.player.getScoreMultiplier(), (0.6, y + h))

            # show the streak counter and miss message
            if self.player.streak > 0 and self.song:
                text = _("%d hit") % self.player.streak
                factor = 0.0
                if self.lastPickPos:
                    diff = self.getSongPosition() - self.lastPickPos
                    if diff > 0 and diff < self.song.period * 2:
                        factor = 0.25 * (1.0 - (diff / (self.song.period * 2))) ** 2
                factor = (1.0 + factor) * 0.002
                tw, th = font.getStringSize(text, scale=factor)
                font.render(text, (0.16 - tw / 2, y + h / 2 - th / 2), scale=factor)
            elif self.lastPickPos is not None and self.countdown <= 0:
                diff = self.getSongPosition() - self.lastPickPos
                alpha = 1.0 - diff * 0.005
                if alpha > 0.1:
                    Theme.setSelectedColor(alpha)
                    glPushMatrix()
                    glTranslate(0.1, y + 0.000005 * diff**2, 0)
                    glRotatef(math.sin(self.lastPickPos) * 25, 0, 0, 1)
                    font.render(_("Missed!"), (0, 0))
                    glPopMatrix()

            # show the streak balls
            if self.player.streak >= 30:
                glColor3f(0.5, 0.5, 1)
            elif self.player.streak >= 20:
                glColor3f(1, 1, 0.5)
            elif self.player.streak >= 10:
                glColor3f(1, 0.5, 0.5)
            else:
                glColor3f(0.5, 1, 0.5)

            s = min(39, self.player.streak) % 10 + 1
            font.render(
                Data.BALL2 * s + Data.BALL1 * (10 - s),
                (0.67, y + h * 1.3),
                scale=0.0011,
            )

            # show multiplier changes
            if self.song and self.lastMultTime is not None:
                diff = self.getSongPosition() - self.lastMultTime
                if diff > 0 and diff < self.song.period * 2:
                    m = self.player.getScoreMultiplier()
                    c = (1, 1, 1)
                    if self.player.streak >= 40:
                        texture = None
                    elif m == 1:
                        texture = None
                    elif m == 2:
                        texture = self.fx2x.texture
                        c = (1, 0.5, 0.5)
                    elif m == 3:
                        texture = self.fx3x.texture
                        c = (1, 1, 0.5)
                    elif m == 4:
                        texture = self.fx4x.texture
                        c = (0.5, 0.5, 1)

                    f = (
                        1.0 - abs(self.song.period * 1 - diff) / (self.song.period * 1)
                    ) ** 2

                    # Flash the screen
                    glBegin(GL_TRIANGLE_STRIP)
                    glColor4f(c[0], c[1], c[2], (f - 0.5) * 1)
                    glVertex2f(0, 0)
                    glColor4f(c[0], c[1], c[2], (f - 0.5) * 1)
                    glVertex2f(1, 0)
                    glColor4f(c[0], c[1], c[2], (f - 0.5) * 0.25)
                    glVertex2f(0, 1)
                    glColor4f(c[0], c[1], c[2], (f - 0.5) * 0.25)
                    glVertex2f(1, 1)
                    glEnd()

                    if texture:
                        glPushMatrix()
                        glEnable(GL_TEXTURE_2D)
                        texture.bind()
                        size = (
                            texture.pixelSize[0] * 0.002,
                            texture.pixelSize[1] * 0.002,
                        )

                        glTranslatef(0.5, 0.15, 0)
                        glBlendFunc(GL_SRC_ALPHA, GL_ONE)

                        f2 = 0.5 + 0.5 * (diff / self.song.period) ** 3
                        glColor4f(1, 1, 1, min(1, 2 - f2))
                        glBegin(GL_TRIANGLE_STRIP)
                        glTexCoord2f(0.0, 0.0)
                        glVertex2f(-size[0] * f2, -size[1] * f2)
                        glTexCoord2f(1.0, 0.0)
                        glVertex2f(size[0] * f2, -size[1] * f2)
                        glTexCoord2f(0.0, 1.0)
                        glVertex2f(-size[0] * f2, size[1] * f2)
                        glTexCoord2f(1.0, 1.0)
                        glVertex2f(size[0] * f2, size[1] * f2)
                        glEnd()

                        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
                        glPopMatrix()

            # show the comments
            if self.song and self.song.info.tutorial:
                glColor3f(1, 1, 1)
                pos = self.getSongPosition()
                for time, event in self.song.track.getEvents(
                    pos - self.song.period * 2, pos + self.song.period * 4
                ):
                    if isinstance(event, PictureEvent):
                        if pos < time or pos > time + event.length:
                            continue

                        try:
                            picture = event.picture
                        except Exception:
                            self.engine.loadSvgDrawing(
                                event,
                                "picture",
                                os.path.join(
                                    self.libraryName, self.songName, event.fileName
                                ),
                            )
                            picture = event.picture

                        wv, hv = self.engine.view.geometry[2:4]
                        fadePeriod = 500.0
                        f = (
                            1.0
                            - min(1.0, abs(pos - time) / fadePeriod)
                            * min(1.0, abs(pos - time - event.length) / fadePeriod)
                        ) ** 2
                        picture.transform.reset()
                        picture.transform.translate(wv / 2, (f * -2 + 1) * hv / 2)
                        picture.transform.scale(1, -1)
                        picture.draw()
                    elif isinstance(event, TextEvent):
                        if pos >= time and pos <= time + event.length:
                            text = _(event.text)
                            wtxt, htxt = font.getStringSize(text)
                            font.render(text, (0.5 - wtxt / 2, 0.67))
        finally:
            self.engine.view.resetProjection()
