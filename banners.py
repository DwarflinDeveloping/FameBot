import colorsys

from PIL import Image
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.cm as cm
from matplotlib import pyplot

# 1. Load and normalize grayscale image
img = Image.open('img.png').convert('L')
gray = np.array(img) / 255.0

# 2. Apply 'copper' colormap
cmap = cm.get_cmap('copper')
bronze_rgba = cmap(gray)                    # M×N×4 array, RGBA in [0,1]
bronze_rgb = (bronze_rgba[..., :3] * 255).astype(np.uint8)

# 3. Blend with grayscale (optional softening)
gray_rgb = np.stack([gray * 255] * 3, axis=-1).astype(np.uint8)
blend_factor = 0.6
blended = (blend_factor * bronze_rgb + (1 - blend_factor) * gray_rgb).astype(np.uint8)

# 4. Increase saturation in HSV space
def increase_saturation(rgb_image, factor=1.5):
    h, w, _ = rgb_image.shape
    rgb_norm = rgb_image / 255.0
    saturated = np.empty_like(rgb_norm)

    for i in range(h):
        for j in range(w):
            r, g, b = rgb_norm[i, j]
            h_val, s, v = colorsys.rgb_to_hsv(r, g, b)
            s = min(s * factor, 1.0)
            r_new, g_new, b_new = colorsys.hsv_to_rgb(h_val, s, v)
            saturated[i, j] = [r_new, g_new, b_new]

    return (saturated * 255).astype(np.uint8)

saturated_img = increase_saturation(blended, factor=3)

# 5. Save or show the result
final_img = Image.fromarray(saturated_img)

# 4. Save or show
final_img.save('output_bronze.jpg')
final_img.show()
