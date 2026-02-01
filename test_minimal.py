# test_minimal.py (na raiz do projeto)
import sys
import os

# garante que "src" entra no path (igual o setup.py fazia)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

import Version
import Config
import Resource
import Log


def main():
    print("Python:", sys.version)
    print("App name:", Version.appName())

    # 1) garante que o diretório "writable" existe
    writable = Resource.getWritableResourcePath()
    print("Writable path:", writable)

    # 2) testa log
    Log.notice("Minimal test: log is working.")
    Log.warn("Minimal test: warn message with accents: ação, coração, ç, ã, é.")

    # 3) define e grava config num ini
    Config.define("test", "volume", int, default=5)
    Config.define("test", "fullscreen", bool, default=False)
    cfg = Config.load(Version.appName() + ".ini", setAsDefault=True)

    print("Config read volume:", cfg.get("test", "volume"))
    print("Config read fullscreen:", cfg.get("test", "fullscreen"))

    cfg.set("test", "volume", 11)
    cfg.set("test", "fullscreen", True)

    print("Config after write volume:", cfg.get("test", "volume"))
    print("Config after write fullscreen:", cfg.get("test", "fullscreen"))

    print("Version string:", Version.version())
    print("Data path:", Version.dataPath())

    print("OK: minimal test finished.")


if __name__ == "__main__":
    main()
