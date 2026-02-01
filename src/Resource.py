# src/Resource.py
#####################################################################
# -*- coding: iso-8859-1 -*-                                        #
#                                                                   #
# Frets on Fire                                                     #
# Copyright (C) 2006 Sami Ky�stil�                                  #
#####################################################################

import os
import time
import shutil
import stat
from threading import Thread, BoundedSemaphore
from queue import Queue, Empty

from Task import Task
import Log
import Version


class Loader(Thread):
    def __init__(
        self, target, name, function, resultQueue, loaderSemaphore, onLoad=None
    ):
        super().__init__()
        self.semaphore = loaderSemaphore
        self.target = target
        self.name = name
        self.function = function
        self.resultQueue = resultQueue
        self.result = None
        self.onLoad = onLoad
        self.exception = None  # will store (exc_type, exc_value, traceback)
        self.time = 0.0
        self.canceled = False
        if target and name:
            setattr(target, name, None)

    # Python 2 compatibility shim: Thread.isAlive() -> Thread.is_alive()
    def isAlive(self):
        return self.is_alive()

    def run(self):
        self.semaphore.acquire()
        try:
            # Reduce priority on posix
            if os.name == "posix":
                try:
                    os.nice(5)
                except Exception:
                    pass
            self.load()
        finally:
            self.semaphore.release()
            self.resultQueue.put(self)

    def __str__(self):
        return "%s(%s) %s" % (
            self.function.__name__,
            self.name,
            "(canceled)" if self.canceled else "",
        )

    def cancel(self):
        self.canceled = True

    def load(self):
        try:
            start = time.time()
            self.result = self.function()
            self.time = time.time() - start
        except Exception:
            import sys

            self.exception = sys.exc_info()

    def finish(self):
        if self.canceled:
            return None

        # target may be None in some uses; guard for readability
        target_name = (
            self.target.__class__.__name__ if self.target is not None else "<None>"
        )
        Log.notice("Loaded %s.%s in %.3f seconds" % (target_name, self.name, self.time))

        if self.exception:
            exc_type, exc_value, tb = self.exception
            # Re-raise with original traceback (Py3 style)
            if exc_value is None:
                raise exc_type
            raise exc_value.with_traceback(tb)

        if self.target and self.name:
            setattr(self.target, self.name, self.result)
        if self.onLoad:
            self.onLoad(self.result)
        return self.result

    def __call__(self):
        self.join()
        return self.result


class Resource(Task):
    def __init__(self, dataPath=os.path.join("..", "data")):
        self.resultQueue = Queue()
        self.dataPaths = [dataPath]
        self.loaderSemaphore = BoundedSemaphore(value=1)
        self.loaders = []

    def addDataPath(self, path):
        if path not in self.dataPaths:
            self.dataPaths = [path] + self.dataPaths

    def removeDataPath(self, path):
        if path in self.dataPaths:
            self.dataPaths.remove(path)

    def fileName(self, *name, **args):
        if not args.get("writable", False):
            readOnlyPath = None
            for dataPath in self.dataPaths:
                readOnlyPath = os.path.join(dataPath, *name)

                # If the requested file is in the read-only path, prefer it.
                if os.path.isfile(readOnlyPath):
                    return readOnlyPath

                # If it exists in the writable path, use that.
                readWritePath = os.path.join(getWritableResourcePath(), *name)
                if os.path.isfile(readWritePath):
                    return readWritePath

            # Fall back to the last computed path (matches original behavior)
            return readOnlyPath
        else:
            readOnlyPath = os.path.join(self.dataPaths[-1], *name)
            try:
                # First see if we can write to the original file
                if os.access(readOnlyPath, os.W_OK):
                    return readOnlyPath
                # If the original file does not exist, see if we can write to its directory
                if (not os.path.isfile(readOnlyPath)) and os.access(
                    os.path.dirname(readOnlyPath), os.W_OK
                ):
                    return readOnlyPath
            except Exception:
                raise

            # If the resource exists in the read-only path, make a copy to the
            # read-write path.
            readWritePath = os.path.join(getWritableResourcePath(), *name)
            if (not os.path.isfile(readWritePath)) and os.path.isfile(readOnlyPath):
                Log.notice("Copying '%s' to writable data directory." % "/".join(name))
                try:
                    os.makedirs(os.path.dirname(readWritePath), exist_ok=True)
                except Exception:
                    pass
                shutil.copy(readOnlyPath, readWritePath)
                self.makeWritable(readWritePath)

            # Create directories if needed
            if (not os.path.isdir(readWritePath)) and os.path.isdir(readOnlyPath):
                Log.notice("Creating writable directory '%s'." % "/".join(name))
                os.makedirs(readWritePath, exist_ok=True)
                self.makeWritable(readWritePath)

            return readWritePath

    def makeWritable(self, path):
        os.chmod(path, stat.S_IWRITE | stat.S_IREAD | stat.S_IEXEC)

    def load(
        self, target=None, name=None, function=lambda: None, synch=False, onLoad=None
    ):
        # Preserve original logging style (but handle target=None safely)
        tname = target.__class__.__name__ if target is not None else "<None>"
        Log.notice(
            "Loading %s.%s %s"
            % (tname, name, "synchronously" if synch else "asynchronously")
        )

        l = Loader(
            target,
            name,
            function,
            self.resultQueue,
            self.loaderSemaphore,
            onLoad=onLoad,
        )
        if synch:
            l.load()
            return l.finish()
        else:
            self.loaders.append(l)
            l.start()
            return l

    def run(self, ticks):
        try:
            loader = self.resultQueue.get_nowait()
            loader.finish()
            self.loaders.remove(loader)
        except Empty:
            pass


def getWritableResourcePath():
    """
    Returns a path that holds the configuration for the application.
    """
    path = "."
    appname = Version.appName()
    if os.name == "posix":
        path = os.path.expanduser("~/." + appname)
    elif os.name == "nt":
        try:
            path = os.path.join(os.environ["APPDATA"], appname)
        except Exception:
            pass
    try:
        os.mkdir(path)
    except Exception:
        pass
    return path
