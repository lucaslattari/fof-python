# src/midi.py
"""
Compat/shim para substituir o antigo pacote "midi" do Frets on Fire (Py2),
usando a biblioteca moderna "mido" para ler/escrever arquivos .mid.

Implementa somente a API que Song.py usa:
- MidiInFile(stream, filename).read()
- MidiOutStream (base com update_time, abs_time, get_current_track)
- MidiOutFile(fileobj) com header/start_of_track/update_time/tempo/note_on/note_off/end_of_track/eof/write
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, BinaryIO, List, Tuple

import mido


class MidiOutStream:
    """
    Base 'stream' compatível com callbacks esperados pelo Song.py.
    O parser (MidiInFile) vai chamar:
      - header(format, nTracks, division)
      - start_of_track()
      - update_time(delta_ticks)
      - tempo(microseconds_per_beat)
      - note_on(channel, note, velocity)
      - note_off(channel, note, velocity)
      - end_of_track()
      - eof()
    """

    def __init__(self):
        self._abs_ticks = 0
        self._current_track = 0
        self._division = 480

    def header(self, format=1, nTracks=1, division=480):
        self._division = int(division)

    def start_of_track(self):
        self._abs_ticks = 0

    def end_of_track(self):
        pass

    def eof(self):
        pass

    def update_time(self, delta_ticks: int):
        self._abs_ticks += int(delta_ticks)

    def abs_time(self) -> int:
        return int(self._abs_ticks)

    def get_current_track(self) -> int:
        return int(self._current_track)

    # eventos padrão (subclasses sobrescrevem)
    def tempo(self, value: int):
        pass

    def note_on(self, channel: int, note: int, velocity: int):
        pass

    def note_off(self, channel: int, note: int, velocity: int):
        pass


class MidiInFile:
    """
    Leitor compatível: recebe um MidiOutStream-like e um path.
    Ao ler, chama callbacks no stream simulando a lib antiga.
    """

    def __init__(self, out_stream: MidiOutStream, filename: str):
        self.out_stream = out_stream
        self.filename = filename

    def read(self):
        mf = mido.MidiFile(self.filename)

        # chama header "global"
        # format: 0/1/2. mido fornece .type
        self.out_stream.header(
            format=mf.type, nTracks=len(mf.tracks), division=mf.ticks_per_beat
        )

        # processa track por track
        for ti, track in enumerate(mf.tracks):
            self.out_stream._current_track = ti
            self.out_stream.start_of_track()

            abs_ticks = 0
            for msg in track:
                # msg.time em mido é delta em ticks (int)
                delta = int(msg.time)
                abs_ticks += delta
                self.out_stream.update_time(delta)

                if msg.type == "set_tempo":
                    # mido usa microseconds_per_beat em msg.tempo
                    self.out_stream.tempo(int(msg.tempo))

                elif msg.type == "note_on":
                    ch = int(getattr(msg, "channel", 0))
                    note = int(msg.note)
                    vel = int(msg.velocity)
                    # note_on vel=0 equivale a note_off
                    if vel == 0:
                        self.out_stream.note_off(ch, note, 0)
                    else:
                        self.out_stream.note_on(ch, note, vel)

                elif msg.type == "note_off":
                    ch = int(getattr(msg, "channel", 0))
                    note = int(msg.note)
                    vel = int(msg.velocity)
                    self.out_stream.note_off(ch, note, vel)

                # demais mensagens são ignoradas (o FoF antigo também não ligava pra maioria)

            self.out_stream.end_of_track()

        self.out_stream.eof()


@dataclass
class _OutEvent:
    abs_tick: int
    msg: mido.Message | mido.MetaMessage


class MidiOutFile:
    """
    Escritor compatível usado por Song.save() e createSong().

    O Song.py chama:
      m = MidiOutFile(f)
      m.header(division=...)
      m.start_of_track()
      m.update_time(t, relative=0)
      m.tempo(microseconds_per_beat)
      m.note_on(...)
      m.note_off(...)
      m.end_of_track()
      m.eof()
      m.write()
    """

    def __init__(self, fileobj: BinaryIO):
        self._fileobj = fileobj
        self._ticks_per_beat = 480
        self._events: List[_OutEvent] = []
        self._cur_abs_tick = 0
        self._started = False

    def header(self, format=1, nTracks=1, division=480):
        self._ticks_per_beat = int(division)

    def start_of_track(self):
        self._started = True
        self._cur_abs_tick = 0

    def update_time(self, value: int, relative: int = 1):
        """
        Lib antiga aceitava relative=0 para setar tempo absoluto.
        Song.py usa relative=0 quase sempre.
        """
        v = int(value)
        if relative == 0:
            self._cur_abs_tick = v
        else:
            self._cur_abs_tick += v

    def tempo(self, value: int):
        # value esperado: microseconds_per_beat (como no Song.py)
        self._events.append(
            _OutEvent(
                self._cur_abs_tick, mido.MetaMessage("set_tempo", tempo=int(value))
            )
        )

    def note_on(self, channel: int, note: int, velocity: int):
        self._events.append(
            _OutEvent(
                self._cur_abs_tick,
                mido.Message(
                    "note_on",
                    channel=int(channel),
                    note=int(note),
                    velocity=int(velocity),
                ),
            )
        )

    def note_off(self, channel: int, note: int):
        self._events.append(
            _OutEvent(
                self._cur_abs_tick,
                mido.Message(
                    "note_off", channel=int(channel), note=int(note), velocity=0
                ),
            )
        )

    def end_of_track(self):
        pass

    def eof(self):
        pass

    def write(self):
        mf = mido.MidiFile(type=1, ticks_per_beat=self._ticks_per_beat)
        tr = mido.MidiTrack()
        mf.tracks.append(tr)

        # ordena por tempo absoluto e converte para deltas
        self._events.sort(key=lambda e: e.abs_tick)

        last = 0
        for e in self._events:
            delta = int(e.abs_tick - last)
            last = int(e.abs_tick)
            msg = e.msg.copy(time=delta)
            tr.append(msg)

        # encerra
        tr.append(mido.MetaMessage("end_of_track", time=0))

        mf.save(file=self._fileobj)
