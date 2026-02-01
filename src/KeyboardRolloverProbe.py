import pygame

pygame.init()
screen = pygame.display.set_mode((400, 200))
pygame.display.set_caption("Teste F1+F3 - Padrão de Gameplay")

print(
    """
INSTRUÇÕES - Simule o padrão do jogo:
1. Segure F1
2. Pressione e solte F3 várias vezes rápido (mantendo F1)
3. Solte F1
4. Agora faça F1+F3 rápido várias vezes (pressiona e solta ambas)
5. ESC para sair

Procurando por F2 fantasma...
"""
)
print("-" * 60)

running = True
f2_ghost_count = 0

while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.KEYDOWN:
            name = pygame.key.name(event.key)
            tick = pygame.time.get_ticks()

            # Detectar F2 fantasma
            if event.key == pygame.K_F2:
                f2_ghost_count += 1
                print(f"!!! F2 DETECTADO !!! (#{f2_ghost_count}) | ticks={tick}")
            else:
                print(f"DOWN: {name:10} | code={event.key} | ticks={tick}")

        elif event.type == pygame.KEYUP:
            name = pygame.key.name(event.key)
            tick = pygame.time.get_ticks()

            if event.key == pygame.K_F2:
                print(f"!!! F2 UP !!!        | ticks={tick}")
            else:
                print(f"UP:   {name:10} | code={event.key} | ticks={tick}")

        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            running = False

print("-" * 60)
print(f"Total de F2 fantasmas detectados: {f2_ghost_count}")
pygame.quit()
