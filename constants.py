from __future__ import annotations


__VERSION__ = "1.0.7"

MAX_COLORS = 10
IMG_SCALES = (0.3, 0.5, 0.7, 0.85, 1, 1.5, 2.1, 3, 4.5, 6.5, 9)
NEUTRAL_ZOOM_IDX = IMG_SCALES.index(1)

IMG_FILES = (".jpg", ".jpeg", ".png")

TAG_LABEL_BG = "#c8c8d2"

PT_BASE_SIZE = 3
PT_MINIMUM_SIZE = 0.5
PT_SELECTED_EXTRA_SIZE = 2
PT_ZOOM_SCALE_FACTOR = 2
PT_OUTLINE_WIDTH = 1

INTERVAL_SAVE = 2000
INTERVAL_POLL = 100
PointsType = tuple[tuple[int, int], tuple[int, int]]
