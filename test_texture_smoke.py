# test_texture_smoke.py
import os
import sys

# Evita o Pygame abrir janela gigante + tenta ocultar (Windows/SDL2)
os.environ.setdefault("SDL_VIDEO_CENTERED", "1")
# Se você estiver rodando em ambiente sem display (CI), isso pode ajudar:
# os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

sys.path.insert(0, "src")


def main():
    import pygame

    # Import do módulo alvo (pega erros de sintaxe/import imediatamente)
    import Texture  # noqa: F401
    from Texture import TextureAtlas, cleanupQueue

    pygame.init()
    pygame.display.init()

    # Cria um contexto OpenGL mínimo.
    # (1x1 funciona na maioria dos drivers; se falhar, tente (64, 64))
    flags = pygame.OPENGL | pygame.DOUBLEBUF
    try:
        screen = pygame.display.set_mode((1, 1), flags)
    except Exception as e:
        print("FAILED: could not create OpenGL context via pygame:", repr(e))
        print("This is usually a driver / OpenGL environment issue, not Texture.py itself.")
        raise

    assert screen is not None

    # Cria um surface RGBA com alpha (atlas usa alphaChannel=True)
    surf = pygame.Surface((32, 32), pygame.SRCALPHA, 32)
    surf.fill((255, 0, 0, 200))
    pygame.draw.circle(surf, (0, 255, 0, 255), (16, 16), 10)

    atlas = TextureAtlas(size=128)
    coords = atlas.add(surf, margin=1)
    atlas.bind()

    # Executa cleanup pendente (se houver) agora que temos contexto válido
    cleaned = 0
    while True:
        try:
            func, args = cleanupQueue.get_nowait()
        except Exception:
            break
        try:
            func(*args)
        except Exception:
            # cleanup não deve matar teste
            pass
        cleaned += 1

    print("Texture smoke test OK.")
    print("Atlas coords:", coords)
    print("Cleanup calls executed:", cleaned)

    pygame.display.quit()
    pygame.quit()


if __name__ == "__main__":
    main()
