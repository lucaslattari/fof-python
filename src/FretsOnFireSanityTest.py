# src/FretsOnFireSanityTest_v2.py
import sys
import time
import traceback

sys.path.insert(0, ".")

from GameEngine import GameEngine
from MainMenu import MainMenu
import Config
import Version


def run_frets_on_fire_sanity(duration=3.0):
    print("=== FretsOnFire sanity test v2 ===")

    events = []

    # -----------------------------
    # Monkey patches (observação profunda)
    # -----------------------------

    # GameEngine.quit
    original_quit = GameEngine.quit

    def quit_probe(self):
        print("[PROBE] engine.quit() CALLED")
        events.append("engine.quit()")
        return original_quit(self)

    GameEngine.quit = quit_probe

    # GameEngine.run
    original_run = GameEngine.run

    def run_probe(self):
        print("[PROBE] engine.run() ENTER")
        result = original_run(self)
        print(f"[PROBE] engine.run() RETURN -> {result}")
        events.append(f"engine.run() -> {result}")
        return result

    GameEngine.run = run_probe

    # MainMenu.shown
    original_shown = MainMenu.shown

    def shown_probe(self):
        print("[PROBE] MainMenu.shown()")
        events.append("MainMenu.shown()")
        return original_shown(self)

    MainMenu.shown = shown_probe

    # MainMenu.hidden
    original_hidden = MainMenu.hidden

    def hidden_probe(self):
        print(
            f"[PROBE] MainMenu.hidden() | nextLayer={getattr(self, 'nextLayer', None)}"
        )
        events.append(f"MainMenu.hidden(nextLayer={getattr(self, 'nextLayer', None)})")
        return original_hidden(self)

    MainMenu.hidden = hidden_probe

    # -----------------------------
    # Execução real
    # -----------------------------
    try:
        print("[TEST] Loading config...")
        config = Config.load(Version.appName() + ".ini", setAsDefault=True)

        print("[TEST] Creating GameEngine...")
        engine = GameEngine(config)

        print("[TEST] Creating MainMenu...")
        menu = MainMenu(engine, songName=None)

        print("[TEST] Setting startup layer...")
        engine.setStartupLayer(menu)

        print(f"[TEST] Entering main loop for ~{duration}s")
        start = time.time()
        iteration = 0

        while True:
            iteration += 1
            print(f"[LOOP] iteration {iteration}")

            if not engine.run():
                print("[LOOP] engine.run() returned False → breaking loop")
                break

            if time.time() - start > duration:
                print("[LOOP] duration exceeded → breaking loop")
                break

        print("[TEST] Main loop exited normally")

    except Exception:
        print("=== EXCEPTION DURING SANITY TEST ===")
        traceback.print_exc()

    finally:
        print("\n=== Sanity report ===")
        if not events:
            print("(!) No events recorded → engine likely exited before loop")
        else:
            for e in events:
                print(" -", e)

        print("\n=== Interpretation guide ===")
        print("* Se engine.run() ENTER aparece apenas uma vez → early exit")
        print("* Se engine.run() retorna False na 1ª iteração → fluxo de shutdown")
        print(
            "* Se MainMenu.hidden() aparece cedo com nextLayer=None → causa confirmada"
        )
        print("* Se engine.quit() aparece sem ação do usuário → lógica herdada do Py2")

        print("\n=== End of sanity test v2 ===")


if __name__ == "__main__":
    run_frets_on_fire_sanity()
