# EditorSanityTest.py
import pygame
import sys
import traceback

from GameEngine import GameEngine
from Editor import Editor


def run_editor_sanity():
    print("=== Editor sanity test ===")

    try:
        print("[0] Initializing engine...")
        engine = GameEngine()

        print("[1] Instantiating Editor...")
        editor = Editor(engine)

        print("[2] Calling editor.run() once...")
        editor.run(ticks=16)

        print("[3] Calling editor.render() once...")
        editor.render(visibility=1.0, topMost=True)

        print("=== Editor sanity test PASSED ===")

    except Exception:
        print("=== Editor sanity test FAILED ===")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    pygame.init()
    run_editor_sanity()
    pygame.quit()
