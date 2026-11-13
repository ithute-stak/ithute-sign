"""Aspect-preserving signature preview rectangle, independent of GUI toolkit."""
def fit_rectangle(x, y, width, height, image_width, image_height):
    if min(width, height, image_width, image_height) <= 0:
        raise ValueError("Image and rectangle dimensions must be positive")
    scale = min(width / image_width, height / image_height)
    actual_width = image_width * scale
    actual_height = image_height * scale
    return (x + (width - actual_width)/2, y + (height - actual_height)/2,
            actual_width, actual_height)
