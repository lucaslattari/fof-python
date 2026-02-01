# src/Config.py
#####################################################################
# -*- coding: iso-8859-1 -*-                                        #
#                                                                   #
# Frets on Fire                                                     #
# Copyright (C) 2006 Sami Ky�stil�                                  #
#####################################################################

import os
import configparser

import Log
import Resource

encoding = "iso-8859-1"

# Global config registry used by Config.get()/Config.set()
config = None

# Prototype registry (schema) for keys defined via Config.define(...)
prototype = {}


class Option:
    """A prototype configuration key."""

    def __init__(self, **args):
        for key, value in args.items():
            setattr(self, key, value)


def define(
    section, option, type, default=None, text=None, options=None, prototype=prototype
):
    """
    Define a configuration key.

    @param section:    Section name
    @param option:     Option name
    @param type:       Key type (e.g. str, int, ...)
    @param default:    Default value for the key
    @param text:       Text description for the key
    @param options:    Either a mapping of values to text descriptions
                       (e.g. {True: 'Yes', False: 'No'}) or a list of possible values
    @param prototype:  Configuration prototype mapping
    """
    if section not in prototype:
        prototype[section] = {}

    if type == bool and not options:
        options = [True, False]

    prototype[section][option] = Option(
        type=type, default=default, text=text, options=options
    )


def load(fileName=None, setAsDefault=True):
    """
    Load a configuration with the default prototype.

    Legacy expectation (Py2-era FoF): calling load() sets the module-global config
    so other modules can call Config.get()/Config.set() without threading a config object around.
    """
    global config
    c = Config(prototype, fileName)

    # Important: In the original codebase, "load()" effectively sets the global config.
    # To keep behavior compatible, set it by default (first load wins),
    # unless the caller explicitly passes setAsDefault=False.
    if setAsDefault:
        if config is None:
            config = c
        else:
            # If caller explicitly wants to replace global config, they can do it manually.
            # We keep "first load wins" to avoid surprising swaps mid-run.
            pass

    return c


class Config:
    """A configuration registry."""

    def __init__(self, prototype, fileName=None):
        """
        @param prototype:  The configuration prototype mapping
        @param fileName:   The file that holds this configuration registry
        """
        self.prototype = prototype
        self.config = configparser.ConfigParser()
        self.fileName = fileName

        if fileName:
            if not os.path.isfile(fileName):
                path = Resource.getWritableResourcePath()
                fileName = os.path.join(path, fileName)
                self.fileName = fileName

            try:
                self.config.read(fileName, encoding=encoding)
            except TypeError:
                # Very old Python 3 fallback
                with open(fileName, "r", encoding=encoding, errors="replace") as f:
                    self.config.read_file(f)

        # Fix defaults and non-existing keys
        for section, options in prototype.items():
            if not self.config.has_section(section):
                self.config.add_section(section)

            for opt_name, opt in options.items():
                if not self.config.has_option(section, opt_name):
                    self.config.set(section, opt_name, str(opt.default))

    def get(self, section, option):
        """
        Read a configuration key.

        @param section:   Section name
        @param option:    Option name
        @return:          Key value
        """
        try:
            opt_type = self.prototype[section][option].type
            default = self.prototype[section][option].default
        except KeyError:
            Log.warn("Config key %s.%s not defined while reading." % (section, option))
            opt_type, default = str, None

        # configparser fallback works for missing keys, but we also guarantee
        # prototype-based default exists because __init__ populates it.
        value = self.config.get(section, option, fallback=default)

        if opt_type == bool:
            v = str(value).lower()
            return v in ("1", "true", "yes", "on")
        else:
            if value is None:
                return None
            return opt_type(value)

    def set(self, section, option, value):
        """
        Set the value of a configuration key.

        @param section:   Section name
        @param option:    Option name
        @param value:     Value
        """
        # warn if not defined, but still allow writing
        try:
            prototype[section][option]
        except KeyError:
            Log.warn("Config key %s.%s not defined while writing." % (section, option))

        if not self.config.has_section(section):
            self.config.add_section(section)

        if value is None:
            svalue = ""
        else:
            svalue = str(value)

        # Preserve legacy iso-8859-1 behavior (ignore unencodable chars)
        svalue = svalue.encode(encoding, "ignore").decode(encoding, "ignore")

        self.config.set(section, option, svalue)

        # Write ini using explicit encoding.
        if not self.fileName:
            path = Resource.getWritableResourcePath()
            self.fileName = os.path.join(path, "FretsOnFire.ini")

        with open(
            self.fileName, "w", encoding=encoding, errors="ignore", newline="\n"
        ) as f:
            self.config.write(f)


def get(section, option):
    """
    Read the value of a global configuration key.

    Robust behavior: if global config isn't loaded yet, load it now.
    """
    global config
    if config is None:
        # This preserves old "global config always exists" assumption
        load(setAsDefault=True)
    return config.get(section, option)


def set(section, option, value):
    """
    Write the value of a global configuration key.

    Robust behavior: if global config isn't loaded yet, load it now.
    """
    global config
    if config is None:
        load(setAsDefault=True)
    config.set(section, option, value)
