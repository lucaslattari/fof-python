#####################################################################
# -*- coding: iso-8859-1 -*-                                        #
#                                                                   #
# Frets on Fire                                                     #
# Copyright (C) 2006 Sami Kytölä                                   #
#####################################################################

import Menu
from Language import _
import Dialogs
import Config
import Mod
import Audio

import pygame


class ConfigChoice(Menu.Choice):
    def __init__(self, config, section, option, autoApply=False):
        self.config = config
        self.section = section
        self.option = option
        self.changed = False
        self.value = None
        self.autoApply = autoApply

        o = config.prototype[section][option]
        v = config.get(section, option)

        if isinstance(o.options, dict):
            # Python 3: dict.values() -> dict_values (não tem sort)
            values = sorted(o.options.values())
            try:
                valueIndex = values.index(o.options[v])
            except (KeyError, ValueError):
                valueIndex = 0

        elif isinstance(o.options, list):
            values = list(o.options)
            try:
                valueIndex = values.index(v)
            except ValueError:
                valueIndex = 0
        else:
            raise RuntimeError(f"No usable options for {section}.{option}.")

        super().__init__(
            text=o.text,
            callback=self.change,
            values=values,
            valueIndex=valueIndex,
        )

    def change(self, value):
        o = self.config.prototype[self.section][self.option]

        if isinstance(o.options, dict):
            for k, v in o.options.items():
                if v == value:
                    value = k
                    break

        self.changed = True
        self.value = value

        if self.autoApply:
            self.apply()

    def apply(self):
        if self.changed:
            self.config.set(self.section, self.option, self.value)


class VolumeConfigChoice(ConfigChoice):
    def __init__(self, engine, config, section, option, autoApply=False):
        super().__init__(config, section, option, autoApply)
        self.engine = engine

    def change(self, value):
        super().change(value)
        sound = self.engine.data.screwUpSound
        sound.setVolume(self.value)
        sound.play()


class KeyConfigChoice(Menu.Choice):
    def __init__(self, engine, config, section, option):
        self.engine = engine
        self.config = config
        self.section = section
        self.option = option
        self.changed = False
        self.value = None
        super().__init__(text="", callback=self.change)

    def getText(self, selected):
        def keycode(k):
            try:
                return int(k)
            except Exception:
                return getattr(pygame, k)

        o = self.config.prototype[self.section][self.option]
        v = self.config.get(self.section, self.option)
        return f"{o.text}: {pygame.key.name(keycode(v)).capitalize()}"

    def change(self):
        o = self.config.prototype[self.section][self.option]

        key = Dialogs.getKey(
            self.engine,
            _("Press a key for '%s' or Escape to cancel.") % o.text,
        )

        if key:
            self.config.set(self.section, self.option, key)
            self.engine.input.reloadControls()

    def apply(self):
        pass


class SettingsMenu(Menu.Menu):
    def __init__(self, engine):
        self.engine = engine
        applyItem = [(_("Apply New Settings"), self.applySettings)]

        modSettings = [
            ConfigChoice(engine.config, "mods", "mod_" + m)
            for m in Mod.getAvailableMods(engine)
        ] + applyItem

        gameSettings = [
            (_("Mod settings"), modSettings),
            ConfigChoice(engine.config, "game", "language"),
            ConfigChoice(engine.config, "game", "leftymode", autoApply=True),
            ConfigChoice(engine.config, "game", "tapping", autoApply=True),
            ConfigChoice(engine.config, "game", "uploadscores", autoApply=True),
            ConfigChoice(engine.config, "game", "compactlist", autoApply=True),
            ConfigChoice(engine.config, "game", "autopreview", autoApply=True),
            ConfigChoice(engine.config, "game", "artistsort", autoApply=True),
        ]
        gameSettingsMenu = Menu.Menu(engine, gameSettings + applyItem)

        keySettings = [
            (_("Test Keys"), lambda: Dialogs.testKeys(engine)),
            KeyConfigChoice(engine, engine.config, "player", "key_action1"),
            KeyConfigChoice(engine, engine.config, "player", "key_action2"),
            KeyConfigChoice(engine, engine.config, "player", "key_1"),
            KeyConfigChoice(engine, engine.config, "player", "key_2"),
            KeyConfigChoice(engine, engine.config, "player", "key_3"),
            KeyConfigChoice(engine, engine.config, "player", "key_4"),
            KeyConfigChoice(engine, engine.config, "player", "key_5"),
            KeyConfigChoice(engine, engine.config, "player", "key_left"),
            KeyConfigChoice(engine, engine.config, "player", "key_right"),
            KeyConfigChoice(engine, engine.config, "player", "key_up"),
            KeyConfigChoice(engine, engine.config, "player", "key_down"),
            KeyConfigChoice(engine, engine.config, "player", "key_cancel"),
        ]
        keySettingsMenu = Menu.Menu(engine, keySettings)

        modes = engine.video.getVideoModes()
        modes = list(modes)
        modes.reverse()

        Config.define(
            "video",
            "resolution",
            str,
            "640x480",
            text=_("Video Resolution"),
            options=[f"{m[0]}x{m[1]}" for m in modes],
        )

        videoSettings = [
            ConfigChoice(engine.config, "video", "resolution"),
            ConfigChoice(engine.config, "video", "fullscreen"),
            ConfigChoice(engine.config, "video", "fps"),
            ConfigChoice(engine.config, "video", "multisamples"),
            ConfigChoice(engine.config, "video", "fontscale"),
        ]
        videoSettingsMenu = Menu.Menu(engine, videoSettings + applyItem)

        volumeSettings = [
            VolumeConfigChoice(engine, engine.config, "audio", "guitarvol"),
            VolumeConfigChoice(engine, engine.config, "audio", "songvol"),
            VolumeConfigChoice(engine, engine.config, "audio", "rhythmvol"),
            VolumeConfigChoice(engine, engine.config, "audio", "screwupvol"),
        ]
        volumeSettingsMenu = Menu.Menu(engine, volumeSettings + applyItem)

        audioSettings = [
            (_("Volume Settings"), volumeSettingsMenu),
            ConfigChoice(engine.config, "audio", "delay"),
            ConfigChoice(engine.config, "audio", "frequency"),
            ConfigChoice(engine.config, "audio", "bits"),
            ConfigChoice(engine.config, "audio", "buffersize"),
        ]
        audioSettingsMenu = Menu.Menu(engine, audioSettings + applyItem)

        settings = [
            (_("Game Settings"), gameSettingsMenu),
            (_("Key Settings"), keySettingsMenu),
            (_("Video Settings"), videoSettingsMenu),
            (_("Audio Settings"), audioSettingsMenu),
        ]

        self.settingsToApply = (
            settings
            + videoSettings
            + audioSettings
            + volumeSettings
            + gameSettings
            + modSettings
        )

        super().__init__(engine, settings)

    def applySettings(self):
        for option in self.settingsToApply:
            if isinstance(option, ConfigChoice):
                option.apply()

        Dialogs.showMessage(
            self.engine,
            _("Settings saved. Please restart the game to activate the new settings."),
        )


class GameSettingsMenu(Menu.Menu):
    def __init__(self, engine):
        settings = [
            VolumeConfigChoice(
                engine, engine.config, "audio", "guitarvol", autoApply=True
            ),
            VolumeConfigChoice(
                engine, engine.config, "audio", "songvol", autoApply=True
            ),
            VolumeConfigChoice(
                engine, engine.config, "audio", "rhythmvol", autoApply=True
            ),
            VolumeConfigChoice(
                engine, engine.config, "audio", "screwupvol", autoApply=True
            ),
        ]
        super().__init__(engine, settings)
