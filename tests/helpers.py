"""Shared test data: a scripted RNG and scenario data sets used by several modules."""

from pygame.math import Vector2

GRID = 20
BLOCKED_TILE = (GRID - 1, 0)  # the tile under the pause button


class ScriptedRng:
    """Stands in for the `random` module so spawn results are predictable.

    choice() returns the next scripted value (which must be one of the offered
    candidates), or the first candidate when the script is empty. random() returns
    the next scripted roll,
    or 0.99 (= "no bomb" for a 50% chance) when the script is empty.
    """

    def __init__(self, choices=(), rolls=()):
        self.choices = list(choices)
        self.rolls = list(rolls)
        self.choice_calls = []

    def choice(self, candidates):
        self.choice_calls.append(list(candidates))
        if self.choices:
            value = self.choices.pop(0)
            assert value in candidates, f"scripted choice {value} is not a candidate"
            return value
        return candidates[0]

    def random(self):
        return self.rolls.pop(0) if self.rolls else 0.99


# name -> (snake cells from head to tail, direction)
SNAKE_LAYOUTS = {
    "initial": ([(5, 10), (4, 10), (3, 10)], (0, 0)),
    "heading_right": ([(6, 10), (5, 10), (4, 10)], (1, 0)),
    "heading_up": ([(10, 10), (10, 11), (10, 12)], (0, -1)),
    "heading_down_at_bottom": ([(10, 18), (10, 17), (10, 16)], (0, 1)),
    "corner_top_left": ([(1, 0), (2, 0), (3, 0)], (-1, 0)),
    "next_to_blocked_tile": ([(18, 1), (17, 1), (16, 1)], (1, 0)),
    "l_shaped": ([(5, 5), (5, 6), (6, 6), (7, 6), (8, 6)], (0, -1)),
    "long_column": ([(2, y) for y in range(15)], (0, 1)),
}

# name -> (snake cells, expected sprite attribute of the middle block)
TURN_LAYOUTS = {
    "vertical": ([(5, 5), (5, 6), (5, 7)], "body_vertical"),
    "horizontal": ([(5, 5), (6, 5), (7, 5)], "body_horizontal"),
    "top_left": ([(5, 5), (5, 6), (4, 6)], "body_tl"),
    "bottom_left": ([(5, 7), (5, 6), (4, 6)], "body_bl"),
    "top_right": ([(5, 5), (5, 6), (6, 6)], "body_tr"),
    "bottom_right": ([(5, 7), (5, 6), (6, 6)], "body_br"),
}


def vectors(cells):
    return [Vector2(cell) for cell in cells]


def board_cells(exclude=()):
    skipped = set(exclude)
    return [(x, y) for y in range(GRID) for x in range(GRID) if (x, y) not in skipped]
