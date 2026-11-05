import pygame

from sim_pitch import FRAME_BORDER_MM, PITCH_LENGTH_MM, draw_pitch
from sim_scorebug import draw_scorebug


WINDOW_SIZE = (1280, 680)
MIN_WINDOW_SIZE = (640, 480)

HOME_TEAM_COLOR = (57, 126, 224)
AWAY_TEAM_COLOR = (218, 74, 62)


def draw_demo(surface: pygame.Surface) -> None:
    field = draw_pitch(surface)
    scale = field.width / PITCH_LENGTH_MM
    frame_height = round(FRAME_BORDER_MM * scale)
    board_top = field.top - frame_height
    scorebug_height = min(30, max(16, frame_height - 6))
    scorebug_top = board_top + (frame_height - scorebug_height) // 2
    draw_scorebug(
        surface,
        home_name="Home United",
        home_score=2,
        home_piece_color=HOME_TEAM_COLOR,
        away_score=1,
        away_piece_color=AWAY_TEAM_COLOR,
        away_name="Away City",
        center_x=field.centerx,
        top=scorebug_top,
        height=scorebug_height,
    )


def main() -> None:
    pygame.init()
    screen = pygame.display.set_mode(WINDOW_SIZE, pygame.RESIZABLE)
    pygame.display.set_caption("Subbuteo Score Bug Preview")
    clock = pygame.time.Clock()
    running = True

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                running = False
            elif event.type == pygame.VIDEORESIZE:
                screen = pygame.display.set_mode(
                    (
                        max(event.w, MIN_WINDOW_SIZE[0]),
                        max(event.h, MIN_WINDOW_SIZE[1]),
                    ),
                    pygame.RESIZABLE,
                )

        draw_demo(screen)
        pygame.display.flip()
        clock.tick(60)

    pygame.quit()


if __name__ == "__main__":
    main()
