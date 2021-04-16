def clamp(value, x1, x2):
    min_value = min(abs(x1), abs(x2))
    max_value = max(abs(x1), abs(x2))
    value = value
    return min(max(value, min_value), max_value)
