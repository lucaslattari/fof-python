# test_keyboard_ghosting_complete.py
import pygame
import sys

pygame.init()
screen = pygame.display.set_mode((900, 700))
pygame.display.set_caption("Teste de Keyboard Ghosting - F1-F5 + BACKSPACE")
font = pygame.font.Font(None, 36)
small_font = pygame.font.Font(None, 24)
tiny_font = pygame.font.Font(None, 20)

# Estado das teclas
keys_state = {
    "F1": False,
    "F2": False,
    "F3": False,
    "F4": False,
    "F5": False,
    "BACKSPACE": False,
}

# Histórico de eventos
event_log = []
max_log_lines = 15

# Contador de sucessos
success_count = 0
ghosting_detected = False

clock = pygame.time.Clock()
running = True

print("=" * 70)
print("TESTE DE KEYBOARD GHOSTING - F1-F5 + BACKSPACE")
print("=" * 70)
print("INSTRUÇÕES:")
print("1. Teste diferentes combinações de F1-F5")
print("2. Mantenha as teclas pressionadas")
print("3. Pressione BACKSPACE")
print()
print("COMBINAÇÕES IMPORTANTES PARA TESTAR:")
print("  - F1 + F3 + BACKSPACE (o caso problemático original)")
print("  - F1 + F2 + BACKSPACE")
print("  - F2 + F4 + BACKSPACE")
print("  - F1 + F2 + F3 + BACKSPACE")
print("  - Todas as 6 teclas juntas")
print()
print("Se BACKSPACE não ficar verde com alguma combinação = GHOSTING!")
print("=" * 70)
print()


def count_pressed_keys():
    return sum(1 for pressed in keys_state.values() if pressed)


while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.KEYDOWN:
            key_name = pygame.key.name(event.key)

            if event.key == pygame.K_F1:
                keys_state["F1"] = True
                msg = f"[DOWN] F1 (keycode {event.key})"
                event_log.append(msg)
                print(msg)
            elif event.key == pygame.K_F2:
                keys_state["F2"] = True
                msg = f"[DOWN] F2 (keycode {event.key})"
                event_log.append(msg)
                print(msg)
            elif event.key == pygame.K_F3:
                keys_state["F3"] = True
                msg = f"[DOWN] F3 (keycode {event.key})"
                event_log.append(msg)
                print(msg)
            elif event.key == pygame.K_F4:
                keys_state["F4"] = True
                msg = f"[DOWN] F4 (keycode {event.key})"
                event_log.append(msg)
                print(msg)
            elif event.key == pygame.K_F5:
                keys_state["F5"] = True
                msg = f"[DOWN] F5 (keycode {event.key})"
                event_log.append(msg)
                print(msg)
            elif event.key == pygame.K_BACKSPACE:
                keys_state["BACKSPACE"] = True
                msg = f"[DOWN] BACKSPACE (keycode {event.key})"
                event_log.append(msg)
                print(msg)

                # Verificar quantas teclas F estão pressionadas
                f_keys_pressed = [
                    k for k in ["F1", "F2", "F3", "F4", "F5"] if keys_state[k]
                ]

                if len(f_keys_pressed) >= 2:
                    success_msg = f"✅ SUCESSO! BACKSPACE + {'+'.join(f_keys_pressed)} detectados!"
                    event_log.append(success_msg)
                    print()
                    print("=" * 70)
                    print(success_msg)
                    print("=" * 70)
                    print()
                    success_count += 1

            elif event.key == pygame.K_ESCAPE:
                running = False

            # Verificar se todas as 6 estão pressionadas
            if all(keys_state.values()):
                all_success_msg = (
                    "🎉 INCRÍVEL! Todas as 6 teclas detectadas simultaneamente!"
                )
                event_log.append(all_success_msg)
                print()
                print("=" * 70)
                print(all_success_msg)
                print("NENHUM GHOSTING DETECTADO COM ESTA COMBINAÇÃO!")
                print("=" * 70)
                print()

        elif event.type == pygame.KEYUP:
            if event.key == pygame.K_F1:
                keys_state["F1"] = False
                msg = f"[UP] F1"
                event_log.append(msg)
                print(msg)
            elif event.key == pygame.K_F2:
                keys_state["F2"] = False
                msg = f"[UP] F2"
                event_log.append(msg)
                print(msg)
            elif event.key == pygame.K_F3:
                keys_state["F3"] = False
                msg = f"[UP] F3"
                event_log.append(msg)
                print(msg)
            elif event.key == pygame.K_F4:
                keys_state["F4"] = False
                msg = f"[UP] F4"
                event_log.append(msg)
                print(msg)
            elif event.key == pygame.K_F5:
                keys_state["F5"] = False
                msg = f"[UP] F5"
                event_log.append(msg)
                print(msg)
            elif event.key == pygame.K_BACKSPACE:
                keys_state["BACKSPACE"] = False
                msg = f"[UP] BACKSPACE"
                event_log.append(msg)
                print(msg)

    # Limitar log
    if len(event_log) > max_log_lines:
        event_log.pop(0)

    # Renderizar
    screen.fill((20, 20, 30))

    # Título
    title = font.render("TESTE DE KEYBOARD GHOSTING", True, (255, 255, 100))
    screen.blit(title, (900 // 2 - title.get_width() // 2, 15))

    # Subtítulo
    subtitle = small_font.render("F1-F5 + BACKSPACE", True, (200, 200, 200))
    screen.blit(subtitle, (900 // 2 - subtitle.get_width() // 2, 50))

    # Instruções
    inst1 = tiny_font.render(
        "Pressione várias teclas F (F1-F5) e depois BACKSPACE", True, (180, 180, 180)
    )
    inst2 = tiny_font.render(
        "Teste principalmente: F1+F3+BACKSPACE", True, (255, 180, 180)
    )
    inst3 = tiny_font.render("ESC para sair", True, (120, 120, 120))
    screen.blit(inst1, (900 // 2 - inst1.get_width() // 2, 80))
    screen.blit(inst2, (900 // 2 - inst2.get_width() // 2, 100))
    screen.blit(inst3, (900 // 2 - inst3.get_width() // 2, 120))

    # Contador de teclas pressionadas
    num_pressed = count_pressed_keys()
    counter_text = f"Teclas pressionadas: {num_pressed}/6"
    if num_pressed >= 3:
        counter_color = (0, 255, 0)
    elif num_pressed >= 1:
        counter_color = (255, 255, 0)
    else:
        counter_color = (150, 150, 150)

    counter = small_font.render(counter_text, True, counter_color)
    screen.blit(counter, (900 // 2 - counter.get_width() // 2, 150))

    # Status das teclas - Layout em grid
    y_start = 200
    x_left = 100
    x_right = 500

    # Coluna esquerda: F1-F3
    y = y_start
    for key_name in ["F1", "F2", "F3"]:
        is_pressed = keys_state[key_name]

        # Fundo da tecla
        rect = pygame.Rect(x_left - 10, y - 5, 350, 50)
        bg_color = (0, 100, 0) if is_pressed else (40, 40, 50)
        pygame.draw.rect(screen, bg_color, rect, border_radius=8)
        pygame.draw.rect(screen, (100, 100, 100), rect, 2, border_radius=8)

        # Texto
        color = (0, 255, 0) if is_pressed else (100, 100, 100)
        status = "PRESSIONADA ✓" if is_pressed else "solta"
        text = font.render(f"{key_name}: {status}", True, color)
        screen.blit(text, (x_left, y))
        y += 60

    # Coluna direita: F4-F5
    y = y_start
    for key_name in ["F4", "F5"]:
        is_pressed = keys_state[key_name]

        # Fundo da tecla
        rect = pygame.Rect(x_right - 10, y - 5, 350, 50)
        bg_color = (0, 100, 0) if is_pressed else (40, 40, 50)
        pygame.draw.rect(screen, bg_color, rect, border_radius=8)
        pygame.draw.rect(screen, (100, 100, 100), rect, 2, border_radius=8)

        # Texto
        color = (0, 255, 0) if is_pressed else (100, 100, 100)
        status = "PRESSIONADA ✓" if is_pressed else "solta"
        text = font.render(f"{key_name}: {status}", True, color)
        screen.blit(text, (x_right, y))
        y += 60

    # BACKSPACE - destaque especial no centro inferior
    y = y_start + 120
    is_pressed = keys_state["BACKSPACE"]

    # Fundo maior para BACKSPACE
    rect = pygame.Rect(200, y - 10, 500, 70)
    bg_color = (0, 150, 0) if is_pressed else (50, 50, 60)
    pygame.draw.rect(screen, bg_color, rect, border_radius=10)
    pygame.draw.rect(screen, (150, 150, 150), rect, 3, border_radius=10)

    color = (0, 255, 0) if is_pressed else (120, 120, 120)
    status = "PRESSIONADA ✓✓✓" if is_pressed else "solta"
    text = font.render(f"BACKSPACE: {status}", True, color)
    screen.blit(text, (900 // 2 - text.get_width() // 2, y + 5))

    # Estatísticas
    stats_y = 420
    stats = tiny_font.render(
        f"Combinações bem-sucedidas: {success_count}", True, (100, 255, 100)
    )
    screen.blit(stats, (50, stats_y))

    # Log de eventos
    log_title = small_font.render("LOG DE EVENTOS:", True, (255, 255, 100))
    screen.blit(log_title, (50, 450))

    y = 480
    for msg in event_log[-10:]:
        if "✅" in msg or "🎉" in msg:
            color = (100, 255, 100)
        elif "[DOWN]" in msg:
            color = (150, 255, 150)
        elif "[UP]" in msg:
            color = (255, 150, 150)
        else:
            color = (200, 200, 200)

        text = tiny_font.render(msg[:80], True, color)
        screen.blit(text, (50, y))
        y += 20

    pygame.display.flip()
    clock.tick(60)

pygame.quit()

# Resumo final
print()
print("=" * 70)
print("TESTE FINALIZADO!")
print("=" * 70)
print(f"Combinações bem-sucedidas detectadas: {success_count}")
print()
if success_count > 0:
    print("✅ BACKSPACE funciona com pelo menos algumas combinações!")
    print("   Você pode usar BACKSPACE como tecla de strum.")
else:
    print("❌ BACKSPACE apresentou ghosting em todas as tentativas.")
    print("   Considere outras alternativas (SPACE, TAB, etc.)")
print("=" * 70)
