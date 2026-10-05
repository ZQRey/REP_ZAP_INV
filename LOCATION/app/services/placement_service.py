"""Choose a free point for newly added map icons."""
import math


def free_position(x, y, occupied, polygon=None):
    def inside(px, py):
        if not polygon:
            return True
        contained = False
        previous = polygon[-1]
        for point in polygon:
            if (point['y'] > py) != (previous['y'] > py):
                crossing = (previous['x'] - point['x']) * (py - point['y']) / (previous['y'] - point['y']) + point['x']
                if px < crossing:
                    contained = not contained
            previous = point
        return contained

    candidates = [(x, y)]
    for radius in (.025, .05, .075, .1, .15):
        candidates.extend((x + radius * math.cos(i * math.pi / 4), y + radius * math.sin(i * math.pi / 4)) for i in range(8))
    for px, py in candidates:
        if 0 <= px <= 1 and 0 <= py <= 1 and inside(px, py) and all(
            ox is None or oy is None or math.hypot(px - ox, py - oy) >= .022 for ox, oy in occupied):
            return round(px, 4), round(py, 4)
    return x, y
