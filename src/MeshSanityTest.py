# src/MeshSanityTest.py

import sys
import pygame
from OpenGL.GL import *

from Mesh import Mesh


def main():
    print("=== Mesh sanity test ===")

    pygame.init()
    pygame.display.set_mode((640, 480), pygame.OPENGL | pygame.DOUBLEBUF)

    print("[TEST] Creating OpenGL context OK")

    # Ajuste o caminho se necessário
    dae_path = "data/cassette.dae"

    print(f"[TEST] Loading mesh: {dae_path}")
    mesh = Mesh(dae_path)

    print("[TEST] Calling render(None)")
    mesh.render(None)

    print("[OK] Mesh rendered without TypeError")

    pygame.quit()
    print("=== Mesh sanity test PASSED ===")


if __name__ == "__main__":
    sys.exit(main())
