import numpy as np

def darken_color(color, factor=0.7):
    """
    Darkens a given color by a specified factor.

    This function is robust and can handle colors provided in two formats:
    1. A hex string (e.g., '#d9534f' or 'd9534f').
    2. An RGB or RGBA tuple where values are floats between 0 and 1 (e.g., (0.85, 0.32, 0.31)).

    Args:
        color (str or tuple): The color to darken.
        factor (float): The factor by which to darken the color. 0 is black, 1 is the original color.

    Returns:
        tuple: The darkened color as an RGB tuple (e.g., (0.59, 0.22, 0.21)).
    """
    try:
        if isinstance(color, str):
            # --- Handle HEX String Input ---
            # Remove '#' and convert 'RRGGBB' to a tuple of integers (0-255)
            hex_code = color.lstrip('#')
            rgb_int = tuple(int(hex_code[i:i + 2], 16) for i in (0, 2, 4))

            # Convert to a tuple of floats (0.0-1.0)
            rgb_float = tuple(c / 255.0 for c in rgb_int)
        else:
            # --- Handle RGB/RGBA Tuple Input ---
            # Assume it's already a float tuple, just take the first 3 (RGB) components
            rgb_float = color[:3]

        # Darken the color by multiplying each component by the factor
        # Use max(0, ...) to ensure the value doesn't go below zero
        darker_rgb_float = tuple(max(0, c * factor) for c in rgb_float)

        return darker_rgb_float

    except Exception as e:
        print(f"Warning: Could not darken color '{color}'. Defaulting to black. Error: {e}")
        return (0, 0, 0)  # Return black as a safe fallback


def tint_color_with_white(color, factor=0.2):
    """
    Tints white with a given color.

    Args:
        color (tuple): The RGB color (floats 0-1) to mix in.
        factor (float): The amount of color to mix with white (0=pure white, 1=pure color).

    Returns:
        tuple: The resulting tinted RGB color.
    """
    white = np.array([1.0, 1.0, 1.0])
    color_np = np.array(color[:3])

    # Linear interpolation between white and the color
    tinted_color = white * (1 - factor) + color_np * factor
    return tuple(tinted_color)