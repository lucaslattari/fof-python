# -*- coding: iso-8859-1 -*-
#####################################################################
# Frets on Fire
# Copyright (C) 2006 Sami K...
#####################################################################

from __future__ import annotations

import os
import re
import shutil
import binascii
import hashlib
from functools import reduce
from configparser import ConfigParser

# urllib (Py3)
from urllib.parse import urlencode
from urllib.request import urlopen

import Log
import Audio
import Config
import Version
import Theme
from Language import _

# --- Optional / legacy deps (keep import-time resilient) -----------------

try:
    import midi
except Exception as e:
    midi = None
    Log.warn(f"midi module not available: {e!r}")

try:
    import Cerealizer  # legacy dependency (often external)
except Exception as e:
    Cerealizer = None
    Log.warn(f"Cerealizer module not available: {e!r}")

DEFAULT_LIBRARY = "songs"

AMAZING_DIFFICULTY = 0
MEDIUM_DIFFICULTY = 1
EASY_DIFFICULTY = 2
SUPAEASY_DIFFICULTY = 3


class Difficulty:
    def __init__(self, id, text):
        self.id = id
        self.text = text

    def __str__(self):
        return self.text

    def __repr__(self):
        return self.text


difficulties = {
    SUPAEASY_DIFFICULTY: Difficulty(SUPAEASY_DIFFICULTY, _("Supaeasy")),
    EASY_DIFFICULTY: Difficulty(EASY_DIFFICULTY, _("Easy")),
    MEDIUM_DIFFICULTY: Difficulty(MEDIUM_DIFFICULTY, _("Medium")),
    AMAZING_DIFFICULTY: Difficulty(AMAZING_DIFFICULTY, _("Amazing")),
}


class SongInfo(object):
    def __init__(self, infoFileName):
        self.songName = os.path.basename(os.path.dirname(infoFileName))
        self.fileName = infoFileName
        self.info = ConfigParser()
        self._difficulties = None

        try:
            # Note: configparser in Py3 handles file reading internally
            self.info.read(infoFileName, encoding=Config.encoding)
        except Exception:
            pass

        # Read highscores and verify their hashes.
        self.highScores = {}

        scores = self._get("scores", str, "")
        if scores:
            if Cerealizer is None:
                Log.warn(
                    "Scores present but Cerealizer is missing; ignoring stored highscores."
                )
            else:
                try:
                    raw = binascii.unhexlify(
                        scores.encode("ascii") if isinstance(scores, str) else scores
                    )
                    scores_obj = Cerealizer.loads(raw)
                    for difficulty in list(scores_obj.keys()):
                        try:
                            diff = difficulties[difficulty]
                        except KeyError:
                            continue
                        for score, stars, name, hsh in scores_obj[diff.id]:
                            if self.getScoreHash(diff, score, stars, name) == hsh:
                                self.addHighscore(diff, score, stars, name)
                            else:
                                Log.warn(
                                    "Weak hack attempt detected. Better luck next time."
                                )
                except Exception as e:
                    Log.warn(f"Failed to read highscores from song.ini: {e!r}")

    def _set(self, attr, value):
        if not self.info.has_section("song"):
            self.info.add_section("song")

        # In Py3, keep config values as str. Preserve legacy encoding.
        if isinstance(value, bytes):
            value = value.decode(Config.encoding, errors="ignore")
        else:
            value = str(value)

        self.info.set("song", attr, value)

    def getObfuscatedScores(self):
        if Cerealizer is None:
            return ""  # cannot serialize scores without Cerealizer

        s = {}
        for difficulty in list(self.highScores.keys()):
            s[difficulty.id] = [
                (score, stars, name, self.getScoreHash(difficulty, score, stars, name))
                for score, stars, name in self.highScores[difficulty]
            ]
        dumped = Cerealizer.dumps(s)
        # hexlify -> bytes; return str for config writing
        return binascii.hexlify(dumped).decode("ascii")

    def save(self):
        self._set("scores", self.getObfuscatedScores())

        with open(self.fileName, "w", encoding=Config.encoding, errors="ignore") as f:
            self.info.write(f)

    def _get(self, attr, type=None, default=""):
        try:
            v = self.info.get("song", attr)
        except Exception:
            v = default
        if v is not None and type:
            v = type(v)
        return v

    def getDifficulties(self):
        # Tutorials only have the medium difficulty
        if self.tutorial:
            return [difficulties[MEDIUM_DIFFICULTY]]

        if self._difficulties is not None:
            return self._difficulties

        # See which difficulties are available
        try:
            if midi is None:
                raise RuntimeError("midi module missing")

            noteFileName = os.path.join(os.path.dirname(self.fileName), "notes.mid")
            info = MidiInfoReader()
            midiIn = midi.MidiInFile(info, noteFileName)
            try:
                midiIn.read()
            except MidiInfoReader.Done:
                pass

            # Sort descending by id (was cmp(b.id, a.id))
            info.difficulties.sort(key=lambda d: d.id, reverse=True)
            self._difficulties = info.difficulties
        except Exception:
            self._difficulties = list(difficulties.values())
        return self._difficulties

    def getName(self):
        return self._get("name")

    def setName(self, value):
        self._set("name", value)

    def getArtist(self):
        return self._get("artist")

    def getCassetteColor(self):
        c = self._get("cassettecolor")
        if c:
            return Theme.hexToColor(c)

    def setCassetteColor(self, color):
        self._set("cassettecolor", Theme.colorToHex(color))

    def setArtist(self, value):
        self._set("artist", value)

    def getScoreHash(self, difficulty, score, stars, name):
        # Old code used sha.sha("%d%d%d%s" % (...)).hexdigest()
        # We'll reproduce the same string input, encoded latin-1 to be stable.
        payload = f"{difficulty.id}{score}{stars}{name}"
        return hashlib.sha1(
            payload.encode(Config.encoding, errors="ignore")
        ).hexdigest()

    def getDelay(self):
        return self._get("delay", int, 0)

    def setDelay(self, value):
        return self._set("delay", value)

    def getHighscores(self, difficulty):
        try:
            return self.highScores[difficulty]
        except KeyError:
            return []

    def uploadHighscores(self, url, songHash):
        try:
            d = {
                "songName": self.songName,
                "songHash": songHash,
                "scores": self.getObfuscatedScores(),
                "version": Version.version(),
            }
            data = urlopen(url + "?" + urlencode(d)).read()
            # server might return bytes
            if isinstance(data, bytes):
                data = data.decode("utf-8", errors="ignore")

            Log.debug("Score upload result: %s" % data)
            fields = data.split(";") if ";" in data else [data, "0"]
            return (fields[0] == "True", int(fields[1]))
        except Exception as e:
            Log.error(e)
            return (False, 0)

    def addHighscore(self, difficulty, score, stars, name):
        if difficulty not in self.highScores:
            self.highScores[difficulty] = []

        self.highScores[difficulty].append((score, stars, name))
        # Sort descending by score
        self.highScores[difficulty].sort(key=lambda t: t[0], reverse=True)
        self.highScores[difficulty] = self.highScores[difficulty][:5]

        for i, scores in enumerate(self.highScores[difficulty]):
            _score, _stars, _name = scores
            if _score == score and _stars == stars and _name == name:
                return i
        return -1

    def isTutorial(self):
        return self._get("tutorial", int, 0) == 1

    name = property(getName, setName)
    artist = property(getArtist, setArtist)
    delay = property(getDelay, setDelay)
    tutorial = property(isTutorial)
    difficulties = property(getDifficulties)
    cassetteColor = property(getCassetteColor, setCassetteColor)


class LibraryInfo(object):
    def __init__(self, libraryName, infoFileName):
        self.libraryName = libraryName
        self.fileName = infoFileName
        self.info = ConfigParser()
        self.songCount = 0

        try:
            self.info.read(infoFileName, encoding=Config.encoding)
        except Exception:
            pass

        # Set a default name
        if not self.name:
            self.name = os.path.basename(os.path.dirname(self.fileName))

        # Count the available songs
        libraryRoot = os.path.dirname(self.fileName)
        for name in os.listdir(libraryRoot):
            if not os.path.isdir(os.path.join(libraryRoot, name)) or name.startswith(
                "."
            ):
                continue
            if os.path.isfile(os.path.join(libraryRoot, name, "song.ini")):
                self.songCount += 1

    def _set(self, attr, value):
        if not self.info.has_section("library"):
            self.info.add_section("library")
        if isinstance(value, bytes):
            value = value.decode(Config.encoding, errors="ignore")
        else:
            value = str(value)
        self.info.set("library", attr, value)

    def save(self):
        with open(self.fileName, "w", encoding=Config.encoding, errors="ignore") as f:
            self.info.write(f)

    def _get(self, attr, type=None, default=""):
        try:
            v = self.info.get("library", attr)
        except Exception:
            v = default
        if v is not None and type:
            v = type(v)
        return v

    def getName(self):
        return self._get("name")

    def setName(self, value):
        self._set("name", value)

    def getColor(self):
        c = self._get("color")
        if c:
            return Theme.hexToColor(c)

    def setColor(self, color):
        self._set("color", Theme.colorToHex(color))

    name = property(getName, setName)
    color = property(getColor, setColor)


class Event:
    def __init__(self, length):
        self.length = length


class Note(Event):
    def __init__(self, number, length, special=False, tappable=False):
        super().__init__(length)
        self.number = number
        self.played = False
        self.special = special
        self.tappable = tappable

    def __repr__(self):
        return "<#%d>" % self.number


class Tempo(Event):
    def __init__(self, bpm):
        super().__init__(0)
        self.bpm = bpm

    def __repr__(self):
        return "<%d bpm>" % self.bpm


class TextEvent(Event):
    def __init__(self, text, length):
        super().__init__(length)
        self.text = text

    def __repr__(self):
        return "<%s>" % self.text


class PictureEvent(Event):
    def __init__(self, fileName, length):
        super().__init__(length)
        self.fileName = fileName


class Track:
    granularity = 50

    def __init__(self):
        self.events = []
        self.allEvents = []

    def addEvent(self, time, event):
        for t in range(
            int(time / self.granularity),
            int((time + event.length) / self.granularity) + 1,
        ):
            if len(self.events) < t + 1:
                n = t + 1 - len(self.events)
                n *= 8
                self.events = self.events + [[] for _ in range(n)]
            self.events[t].append((time - (t * self.granularity), event))
        self.allEvents.append((time, event))

    def removeEvent(self, time, event):
        for t in range(
            int(time / self.granularity),
            int((time + event.length) / self.granularity) + 1,
        ):
            e = (time - (t * self.granularity), event)
            if t < len(self.events) and e in self.events[t]:
                self.events[t].remove(e)
        if (time, event) in self.allEvents:
            self.allEvents.remove((time, event))

    def getEvents(self, startTime, endTime):
        t1, t2 = [
            int(x) for x in [startTime / self.granularity, endTime / self.granularity]
        ]
        if t1 > t2:
            t1, t2 = t2, t1

        events = set()
        for t in range(max(t1, 0), min(len(self.events), t2)):
            for diff, event in self.events[t]:
                time = (self.granularity * t) + diff
                events.add((time, event))
        return events

    def getAllEvents(self):
        return self.allEvents

    def reset(self):
        for eventList in self.events:
            for _time, event in eventList:
                if isinstance(event, Note):
                    event.played = False

    def update(self):
        bpm = None
        ticksPerBeat = 480
        tickThreshold = 161
        prevNotes = []
        currentNotes = []
        currentTicks = 0.0
        prevTicks = 0.0
        epsilon = 1e-3

        def beatsToTicks(time):
            return (time * bpm * ticksPerBeat) / 60000.0

        if not self.allEvents:
            return

        for time, event in self.allEvents + [self.allEvents[-1]]:
            if isinstance(event, Tempo):
                bpm = event.bpm
            elif isinstance(event, Note):
                event.tappable = False
                ticks = beatsToTicks(time)

                # chord?
                if ticks < currentTicks + epsilon:
                    currentNotes.append(event)
                    continue

                # Previous note not a chord?
                if len(prevNotes) == 1:
                    prevEndTicks = prevTicks + beatsToTicks(prevNotes[0].length)
                    if currentTicks - prevEndTicks <= tickThreshold:
                        for note in currentNotes:
                            if note.number == prevNotes[0].number:
                                break
                        else:
                            for note in currentNotes:
                                note.tappable = True

                prevNotes = currentNotes
                prevTicks = currentTicks
                currentNotes = [event]
                currentTicks = ticks


class Song(object):
    def __init__(
        self,
        engine,
        infoFileName,
        songTrackName,
        guitarTrackName,
        rhythmTrackName,
        noteFileName,
        scriptFileName=None,
    ):
        self.engine = engine
        self.info = SongInfo(infoFileName)
        self.tracks = [Track() for _ in range(len(difficulties))]
        self.difficulty = difficulties[AMAZING_DIFFICULTY]
        self._playing = False
        self.start = 0.0
        self.noteFileName = noteFileName
        self.bpm = None
        self.period = 0

        # load the tracks
        if songTrackName:
            self.music = Audio.Music(songTrackName)

        self.guitarTrack = None
        self.rhythmTrack = None

        try:
            if guitarTrackName:
                self.guitarTrack = Audio.StreamingSound(
                    self.engine, self.engine.audio.getChannel(1), guitarTrackName
                )
        except Exception as e:
            Log.warn("Unable to load guitar track: %s" % e)

        try:
            if rhythmTrackName:
                self.rhythmTrack = Audio.StreamingSound(
                    self.engine, self.engine.audio.getChannel(2), rhythmTrackName
                )
        except Exception as e:
            Log.warn("Unable to load rhythm track: %s" % e)

        # load the notes
        if noteFileName:
            if midi is None:
                raise RuntimeError("midi module missing; cannot load notes.mid")
            midiIn = midi.MidiInFile(MidiReader(self), noteFileName)
            midiIn.read()

        # load the script
        if scriptFileName and os.path.isfile(scriptFileName):
            with open(
                scriptFileName, "r", encoding=Config.encoding, errors="ignore"
            ) as sf:
                scriptReader = ScriptReader(self, sf)
                scriptReader.read()

        # update all note tracks
        for track in self.tracks:
            track.update()

    def getHash(self):
        h = hashlib.sha1()
        with open(self.noteFileName, "rb") as f:
            while True:
                data = f.read(1024)
                if not data:
                    break
                h.update(data)
        return h.hexdigest()

    def setBpm(self, bpm):
        self.bpm = bpm
        self.period = 60000.0 / self.bpm

    def save(self):
        self.info.save()
        with open(self.noteFileName + ".tmp", "wb") as f:
            if midi is None:
                raise RuntimeError("midi module missing; cannot write notes.mid")
            midiOut = MidiWriter(self, midi.MidiOutFile(f))
            midiOut.write()

        shutil.move(self.noteFileName + ".tmp", self.noteFileName)

    def play(self, start=0.0):
        self.start = start
        self.music.play(0, start / 1000.0)
        if self.guitarTrack:
            assert start == 0.0
            self.guitarTrack.play()
        if self.rhythmTrack:
            assert start == 0.0
            self.rhythmTrack.play()
        self._playing = True

    def pause(self):
        self.music.pause()
        self.engine.audio.pause()

    def unpause(self):
        self.music.unpause()
        self.engine.audio.unpause()

    def setGuitarVolume(self, volume):
        if not self.rhythmTrack:
            volume = max(0.1, volume)
        if self.guitarTrack:
            self.guitarTrack.setVolume(volume)
        else:
            self.music.setVolume(volume)

    def setRhythmVolume(self, volume):
        if self.rhythmTrack:
            self.rhythmTrack.setVolume(volume)

    def setBackgroundVolume(self, volume):
        self.music.setVolume(volume)

    def stop(self):
        for track in self.tracks:
            track.reset()

        self.music.stop()
        self.music.rewind()
        if self.guitarTrack:
            self.guitarTrack.stop()
        if self.rhythmTrack:
            self.rhythmTrack.stop()
        self._playing = False

    def fadeout(self, time):
        for track in self.tracks:
            track.reset()

        self.music.fadeout(time)
        if self.guitarTrack:
            self.guitarTrack.fadeout(time)
        if self.rhythmTrack:
            self.rhythmTrack.fadeout(time)
        self._playing = False

    def getPosition(self):
        if not self._playing:
            pos = 0.0
        else:
            pos = self.music.getPosition()
        if pos < 0.0:
            pos = 0.0
        return pos + self.start

    def isPlaying(self):
        return self._playing and self.music.isPlaying()

    def getBeat(self):
        return self.getPosition() / self.period

    def update(self, ticks):
        pass

    def getTrack(self):
        return self.tracks[self.difficulty.id]

    track = property(getTrack)


noteMap = {
    0x60: (AMAZING_DIFFICULTY, 0),
    0x61: (AMAZING_DIFFICULTY, 1),
    0x62: (AMAZING_DIFFICULTY, 2),
    0x63: (AMAZING_DIFFICULTY, 3),
    0x64: (AMAZING_DIFFICULTY, 4),
    0x54: (MEDIUM_DIFFICULTY, 0),
    0x55: (MEDIUM_DIFFICULTY, 1),
    0x56: (MEDIUM_DIFFICULTY, 2),
    0x57: (MEDIUM_DIFFICULTY, 3),
    0x58: (MEDIUM_DIFFICULTY, 4),
    0x48: (EASY_DIFFICULTY, 0),
    0x49: (EASY_DIFFICULTY, 1),
    0x4A: (EASY_DIFFICULTY, 2),
    0x4B: (EASY_DIFFICULTY, 3),
    0x4C: (EASY_DIFFICULTY, 4),
    0x3C: (SUPAEASY_DIFFICULTY, 0),
    0x3D: (SUPAEASY_DIFFICULTY, 1),
    0x3E: (SUPAEASY_DIFFICULTY, 2),
    0x3F: (SUPAEASY_DIFFICULTY, 3),
    0x40: (SUPAEASY_DIFFICULTY, 4),
}

reverseNoteMap = {v: k for k, v in noteMap.items()}


class MidiWriter:
    def __init__(self, song, out):
        self.song = song
        self.out = out
        self.ticksPerBeat = 480

    def midiTime(self, time):
        return int(self.song.bpm * self.ticksPerBeat * time / 60000.0)

    def write(self):
        self.out.header(division=self.ticksPerBeat)
        self.out.start_of_track()
        self.out.update_time(0)

        bpm = self.song.bpm if self.song.bpm else 122.0
        self.out.tempo(int(60.0 * 10.0**6 / bpm))

        # Collect all events
        events = [
            list(zip([difficulty] * len(track.getAllEvents()), track.getAllEvents()))
            for difficulty, track in enumerate(self.song.tracks)
        ]
        events = reduce(lambda a, b: a + b, events, [])
        # Sort by event time
        events.sort(key=lambda item: item[1][0])

        heldNotes = []

        for difficulty, event in events:
            time, event = event
            if isinstance(event, Note):
                time = self.midiTime(time)

                # Turn off any held notes that were active before this point in time
                for note, endTime in list(heldNotes):
                    if endTime <= time:
                        self.out.update_time(endTime, relative=0)
                        self.out.note_off(0, note)
                        heldNotes.remove((note, endTime))

                note = reverseNoteMap[(difficulty, event.number)]
                self.out.update_time(time, relative=0)
                self.out.note_on(0, note, 127 if event.special else 100)
                heldNotes.append((note, time + self.midiTime(event.length)))
                heldNotes.sort(key=lambda x: x[1])

        # Turn off any remaining notes
        for note, endTime in heldNotes:
            self.out.update_time(endTime, relative=0)
            self.out.note_off(0, note)

        self.out.update_time(0)
        self.out.end_of_track()
        self.out.eof()
        self.out.write()


class ScriptReader:
    def __init__(self, song, scriptFile):
        self.song = song
        self.file = scriptFile

    def read(self):
        for line in self.file:
            if line.startswith("#"):
                continue
            time, length, type, data = re.split(r"[\t ]+", line.strip(), 3)
            time = float(time)
            length = float(length)

            if type == "text":
                event = TextEvent(data, length)
            elif type == "pic":
                event = PictureEvent(data, length)
            else:
                continue

            for track in self.song.tracks:
                track.addEvent(time, event)


class MidiReader(midi.MidiOutStream if midi else object):
    def __init__(self, song):
        if midi:
            midi.MidiOutStream.__init__(self)
        self.song = song
        self.heldNotes = {}
        self.velocity = {}
        self.ticksPerBeat = 480
        self.tempoMarkers = []

    def addEvent(self, track, event, time=None):
        if time is None:
            time = self.abs_time()
        assert time >= 0
        if track is None:
            for t in self.song.tracks:
                t.addEvent(time, event)
        elif track < len(self.song.tracks):
            self.song.tracks[track].addEvent(time, event)

    def abs_time(self):
        def ticksToBeats(ticks, bpm):
            return (60000.0 * ticks) / (bpm * self.ticksPerBeat)

        if self.song.bpm and midi:
            currentTime = midi.MidiOutStream.abs_time(self)

            scaledTime = 0.0
            tempoMarkerTime = 0.0
            currentBpm = self.song.bpm
            for time, bpm in self.tempoMarkers:
                if time > currentTime:
                    break
                scaledTime += ticksToBeats(time - tempoMarkerTime, currentBpm)
                tempoMarkerTime, currentBpm = time, bpm
            return scaledTime + ticksToBeats(currentTime - tempoMarkerTime, currentBpm)
        return 0.0

    def header(self, format, nTracks, division):
        self.ticksPerBeat = division

    def tempo(self, value):
        bpm = 60.0 * 10.0**6 / value
        if midi:
            self.tempoMarkers.append((midi.MidiOutStream.abs_time(self), bpm))
        if not self.song.bpm:
            self.song.setBpm(bpm)
        self.addEvent(None, Tempo(bpm))

    def note_on(self, channel, note, velocity):
        if not midi:
            return
        if self.get_current_track() > 1:
            return
        self.velocity[note] = velocity
        self.heldNotes[(self.get_current_track(), channel, note)] = self.abs_time()

    def note_off(self, channel, note, velocity):
        if not midi:
            return
        if self.get_current_track() > 1:
            return
        try:
            startTime = self.heldNotes[(self.get_current_track(), channel, note)]
            endTime = self.abs_time()
            del self.heldNotes[(self.get_current_track(), channel, note)]
            if note in noteMap:
                track, number = noteMap[note]
                self.addEvent(
                    track,
                    Note(
                        number,
                        endTime - startTime,
                        special=(self.velocity.get(note) == 127),
                    ),
                    time=startTime,
                )
            else:
                pass
        except KeyError:
            Log.warn(
                "MIDI note 0x%x on channel %d ending at %d was never started."
                % (note, channel, self.abs_time())
            )


class MidiInfoReader(midi.MidiOutStream if midi else object):
    class Done(Exception):
        pass

    def __init__(self):
        if midi:
            midi.MidiOutStream.__init__(self)
        self.difficulties = []

    def note_on(self, channel, note, velocity):
        try:
            track, _number = noteMap[note]
            diff = difficulties[track]
            if diff not in self.difficulties:
                self.difficulties.append(diff)
                if len(self.difficulties) == len(difficulties):
                    raise MidiInfoReader.Done()
        except KeyError:
            pass


def loadSong(
    engine,
    name,
    library=DEFAULT_LIBRARY,
    seekable=False,
    playbackOnly=False,
    notesOnly=False,
):
    guitarFile = engine.resource.fileName(library, name, "guitar.ogg")
    songFile = engine.resource.fileName(library, name, "song.ogg")
    rhythmFile = engine.resource.fileName(library, name, "rhythm.ogg")
    noteFile = engine.resource.fileName(library, name, "notes.mid", writable=True)
    infoFile = engine.resource.fileName(library, name, "song.ini", writable=True)
    scriptFile = engine.resource.fileName(library, name, "script.txt")

    if seekable:
        if os.path.isfile(guitarFile) and os.path.isfile(songFile):
            songFile = guitarFile
            guitarFile = None
        else:
            songFile = guitarFile
            guitarFile = None

    if not os.path.isfile(songFile):
        songFile = guitarFile
        guitarFile = None

    if not os.path.isfile(rhythmFile):
        rhythmFile = None

    if playbackOnly:
        noteFile = None

    song = Song(
        engine, infoFile, songFile, guitarFile, rhythmFile, noteFile, scriptFile
    )
    return song


def loadSongInfo(engine, name, library=DEFAULT_LIBRARY):
    infoFile = engine.resource.fileName(library, name, "song.ini", writable=True)
    return SongInfo(infoFile)


def createSong(
    engine,
    name,
    guitarTrackName,
    backgroundTrackName,
    rhythmTrackName=None,
    library=DEFAULT_LIBRARY,
):
    path = os.path.abspath(engine.resource.fileName(library, name, writable=True))
    os.makedirs(path, exist_ok=True)

    guitarFile = engine.resource.fileName(library, name, "guitar.ogg", writable=True)
    songFile = engine.resource.fileName(library, name, "song.ogg", writable=True)
    noteFile = engine.resource.fileName(library, name, "notes.mid", writable=True)
    infoFile = engine.resource.fileName(library, name, "song.ini", writable=True)

    shutil.copy(guitarTrackName, guitarFile)

    if backgroundTrackName:
        shutil.copy(backgroundTrackName, songFile)
    else:
        songFile = guitarFile
        guitarFile = None

    if rhythmTrackName:
        rhythmFile = engine.resource.fileName(
            library, name, "rhythm.ogg", writable=True
        )
        shutil.copy(rhythmTrackName, rhythmFile)
    else:
        rhythmFile = None

    if midi is None:
        raise RuntimeError("midi module missing; cannot create notes.mid")

    with open(noteFile, "wb") as f:
        m = midi.MidiOutFile(f)
        m.header()
        m.start_of_track()
        m.update_time(0)
        m.end_of_track()
        m.eof()
        m.write()

    song = Song(engine, infoFile, songFile, guitarFile, rhythmFile, noteFile)
    song.info.name = name
    song.save()

    return song


def getDefaultLibrary(engine):
    return LibraryInfo(
        DEFAULT_LIBRARY, engine.resource.fileName(DEFAULT_LIBRARY, "library.ini")
    )


def getAvailableLibraries(engine, library=DEFAULT_LIBRARY):
    songRoots = [
        engine.resource.fileName(library),
        engine.resource.fileName(library, writable=True),
    ]
    libraries = []
    libraryRoots = []

    for songRoot in songRoots:
        if not os.path.isdir(songRoot):
            continue
        for libraryRoot in os.listdir(songRoot):
            libraryRoot = os.path.join(songRoot, libraryRoot)
            if not os.path.isdir(libraryRoot):
                continue
            for name in os.listdir(libraryRoot):
                if (
                    os.path.isfile(os.path.join(libraryRoot, name, "song.ini"))
                    or name == "library.ini"
                ):
                    if libraryRoot not in libraryRoots:
                        libName = library + os.path.join(
                            libraryRoot.replace(songRoot, "")
                        )
                        libraries.append(
                            LibraryInfo(
                                libName, os.path.join(libraryRoot, "library.ini")
                            )
                        )
                        libraryRoots.append(libraryRoot)
                        break

    libraries.sort(key=lambda a: a.name)
    return libraries


def getAvailableSongs(engine, library=DEFAULT_LIBRARY, includeTutorials=False):
    songRoots = [
        engine.resource.fileName(library),
        engine.resource.fileName(library, writable=True),
    ]
    names = []
    for songRoot in songRoots:
        if not os.path.isdir(songRoot):
            continue
        for name in os.listdir(songRoot):
            if not os.path.isfile(
                os.path.join(songRoot, name, "song.ini")
            ) or name.startswith("."):
                continue
            if name not in names:
                names.append(name)

    songs = [
        SongInfo(engine.resource.fileName(library, name, "song.ini", writable=True))
        for name in names
    ]
    if not includeTutorials:
        songs = [song for song in songs if not song.tutorial]
    songs.sort(key=lambda s: s.name)
    return songs
