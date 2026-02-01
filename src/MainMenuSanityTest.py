# src/MainMenuSanityTest.py
import time
import sys

import pygame

import Config
import Version
import Log
from GameEngine import GameEngine
from MainMenu import MainMenu


def run_sanity(seconds: float = 6.0) -> int:
    print("=== MainMenu sanity test ===")
    print(f"Running for {seconds:.1f}s (ESC to quit early)")

    # Config global precisa existir (Svg/Config.get dependem)
    config = Config.load(Version.appName() + ".ini", setAsDefault=True)

    e = None
    try:
        e = GameEngine(config)
        menu = MainMenu(e, songName=None)
        e.setStartupLayer(menu)

        t0 = time.time()
        while True:
            # Se o engine retornar False, ele quer sair
            if not e.run():
                break

            # ESC pra sair mais cedo (sem depender de menus)
            keys = pygame.key.get_pressed()
            if keys[pygame.K_ESCAPE]:
                break

            if (time.time() - t0) >= seconds:
                break

        print("MainMenu sanity test OK ✅")
        return 0

    except Exception as ex:
        print("MainMenu sanity test FAILED with exception:")
        print(f"{type(ex).__name__}: {ex}")
        import traceback

        traceback.print_exc()
        return 2

    finally:
        if e is not None:
            try:
                e.quit()
            except Exception:
                pass
        pygame.quit()


if __name__ == "__main__":
    raise SystemExit(run_sanity())
