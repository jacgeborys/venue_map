# Create this new file at: utils/color_utils.py

def darken_color(hex_color, factor=0.5):
    """
    Darkens a hex color by a specified factor.

    Args:
        hex_color (str): The color in hex format (e.g., '#FF69B4').
        factor (float): How much to darken. 0.0 means no change,
                        1.0 means black. 0.5 is 50% darker.

    Returns:
        str: The new, darker hex color.
    """
    if not 0 <= factor <= 1:
        raise ValueError("Factor must be between 0 and 1.")

    # Remove '#' if it exists
    hex_color = hex_color.lstrip('#')

    # Convert hex to RGB integers
    rgb = tuple(int(hex_color[i:i + 2], 16) for i in (0, 2, 4))

    # Create the new, darker RGB tuple
    new_rgb = tuple(int(c * (1 - factor)) for c in rgb)

    # Convert new RGB back to hex
    return "#{:02x}{:02x}{:02x}".format(*new_rgb)