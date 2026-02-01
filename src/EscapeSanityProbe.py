# src/EscapeSanityProbe.py
import pygame

import Log
import Config
import Version
from GameEngine import GameEngine
from MainMenu import MainMenu
from View import BackgroundLayer


class EscapeProbe(BackgroundLayer):
    def __init__(self, engine):
        super().__init__()
        self.engine = engine
        self._debugSticky = True  # não sai no popAllLayers
        self._debugAlwaysOnTop = False  # não precisa ficar por cima

    def shown(self):
        Log.notice("[PROBE] EscapeProbe ativo (sticky background)")

    def hidden(self):
        Log.notice(
            "[PROBE] EscapeProbe hidden() (isso não deveria acontecer se sticky)"
        )

    def run(self, ticks):
        # Observa eventos SEM consumir (não chama pygame.event.get() global aqui!)
        # A maioria dos engines já puxa eventos num lugar central.
        # Então aqui fazemos polling leve com pygame.key.get_pressed().
        keys = pygame.key.get_pressed()
        if keys[pygame.K_ESCAPE]:
            # Dump do stack atual
            stack = [
                l.__class__.__name__ for l in getattr(self.engine.view, "layers", [])
            ]
            Log.notice(f"[PROBE] ESC detectado. View stack: {stack}")

    def render(self, visibility, topMost):
        # não desenha nada
        return


def main():
    Log.quiet = False

    config = Config.load(Version.appName() + ".ini", setAsDefault=True)
    engine = GameEngine(config)

    menu = MainMenu(engine, songName=None)
    engine.setStartupLayer(menu)

    # Só agora que o engine tem startup layer, a gente injeta o probe.
    # E como é sticky background, ele não deve sumir.
    engine.view.pushLayer(EscapeProbe(engine))

    try:
        while engine.run():
            pass
    except KeyboardInterrupt:
        pass
    finally:
        engine.quit()


if __name__ == "__main__":
    raise SystemExit(main())
