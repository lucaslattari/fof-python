# src/GameEngineSanityTest.py
import os
import sys
import time
import traceback

# Garante imports do src
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import pygame
from OpenGL.GL import (
    glClearColor,
    glClear,
    GL_COLOR_BUFFER_BIT,
    GL_DEPTH_BUFFER_BIT,
    glBegin,
    glEnd,
    glVertex2f,
    glColor3f,
    GL_TRIANGLES,
    glViewport,
    glGetIntegerv,
    GL_VIEWPORT,
    glFlush,
    glFinish,
    glReadPixels,
    GL_RGBA,
    GL_UNSIGNED_BYTE,
)
from GameEngine import GameEngine
import Log


def _draw_test_triangle(t: float):
    """
    Desenha um triângulo colorido 2D bem simples.
    Se isso aparece, OpenGL + swap buffers estão vivos.
    """
    # fundo oscilando de leve só pra dar vida
    base = 0.10
    pulse = 0.05 * (1.0 + (time.time() % 1.0))
    glClearColor(base + pulse, base, base + pulse * 0.5, 1.0)
    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

    glBegin(GL_TRIANGLES)
    glColor3f(1.0, 0.2, 0.2)
    glVertex2f(-0.6, -0.4)

    glColor3f(0.2, 1.0, 0.2)
    glVertex2f(0.6, -0.4)

    glColor3f(0.2, 0.6, 1.0)
    glVertex2f(0.0, 0.7)
    glEnd()

    glFlush()


def _maybe_screenshot(path: str):
    """
    Tira um screenshot simples com glReadPixels.
    Isso prova que framebuffer está acessível.
    """
    try:
        viewport = glGetIntegerv(GL_VIEWPORT)
        x, y, w, h = (
            int(viewport[0]),
            int(viewport[1]),
            int(viewport[2]),
            int(viewport[3]),
        )

        # ReadPixels dá a imagem invertida verticalmente; vamos salvar assim mesmo (sanity test)
        data = glReadPixels(x, y, w, h, GL_RGBA, GL_UNSIGNED_BYTE)

        # pygame.image.frombuffer espera bytes; data geralmente já é bytes
        surf = pygame.image.frombuffer(data, (w, h), "RGBA")
        pygame.image.save(surf, path)
        return True
    except Exception:
        return False


def run_sanity(
    seconds: float = 5.0,
    fps_target: int = 60,
    take_screenshot: bool = True,
    screenshot_path: str = "sanity_screenshot.png",
):
    """
    Smoke test "pomposo":
    - sobe o GameEngine (janela/GL/áudio/etc)
    - roda loop por alguns segundos
    - desenha triângulo OpenGL por cima
    - permite fechar com ESC / QUIT
    """
    print("=== GameEngine pomposo sanity test ===")
    print(f"Running for {seconds:.1f}s (ESC to quit early)")

    e = None
    clock = pygame.time.Clock()
    t0 = time.time()
    frame = 0
    screenshot_done = False

    try:
        e = GameEngine()

        # Ajusta viewport com base no modo atual (por garantia)
        viewport = glGetIntegerv(GL_VIEWPORT)
        glViewport(
            int(viewport[0]), int(viewport[1]), int(viewport[2]), int(viewport[3])
        )

        # Loop principal
        while True:
            now = time.time()
            elapsed = now - t0

            # quebra por tempo
            if elapsed >= seconds:
                break

            # processa eventos "crus" do pygame também, pra garantir que ESC funcione
            # (o Input do jogo também pega eventos, mas aqui a gente quer um "kill switch" garantido)
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    return 0
                if ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
                    return 0

            # roda o loop do motor (isso chama Engine.run, input, view, etc.)
            done = e.run()
            if done:
                break

            # desenha algo "por cima" como prova de vida do GL
            _draw_test_triangle(elapsed)

            # flip buffer
            # GameEngine.main/loading já chamam self.video.flip().
            # Mas a gente desenhou depois do flip que acontece dentro de e.run().
            # Então: forçamos um flip extra aqui pra garantir que nosso triângulo apareça.
            try:
                e.video.flip()
            except Exception:
                # se flip extra for problema, ao menos não mata o teste
                pass

            # screenshot uma vez (depois de alguns frames)
            if take_screenshot and (not screenshot_done) and frame > 10:
                ok = _maybe_screenshot(os.path.join(HERE, screenshot_path))
                screenshot_done = True
                print(f"Screenshot saved? {ok} -> {screenshot_path}")

            frame += 1
            clock.tick(fps_target)

        return 0

    except Exception as exc:
        print("Sanity test FAILED with exception:")
        print(f"{exc.__class__.__name__}: {exc}")
        traceback.print_exc()
        return 1

    finally:
        if e is not None:
            try:
                e.quit()
            except Exception:
                pass
        try:
            pygame.quit()
        except Exception:
            pass
        print("=== Sanity test finished ===")


if __name__ == "__main__":
    raise SystemExit(run_sanity())
