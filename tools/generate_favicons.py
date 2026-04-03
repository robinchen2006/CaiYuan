from PIL import Image
import os

# Paths
root = os.path.dirname(os.path.dirname(__file__))
src = os.path.join(root, "caiyun_icon.jpg")
static_dir = os.path.join(root, "static")
# If the source JPG isn't at project root, fall back to static/caiyun_icon.jpg
if not os.path.exists(src):
    alt = os.path.join(static_dir, "caiyun_icon.jpg")
    if os.path.exists(alt):
        src = alt
    else:
        raise FileNotFoundError(f"Source icon not found at {src} or {alt}")
icons_dir = os.path.join(static_dir, "icons")

os.makedirs(icons_dir, exist_ok=True)

# Sizes to generate
png_sizes = [16, 32, 48, 64, 96, 192, 256]

# Open source image
img = Image.open(src).convert("RGBA")


# If image is not square, crop the longer side centered to make it square
def crop_center_square(image: Image.Image) -> Image.Image:
    w, h = image.size
    if w == h:
        return image
    if w > h:
        left = (w - h) // 2
        right = left + h
        box = (left, 0, right, h)
    else:
        top = (h - w) // 2
        bottom = top + w
        box = (0, top, w, bottom)
    return image.crop(box)


# Work with a square source for all generated icons to avoid stretching
square_img = crop_center_square(img)

# Generate PNGs
png_paths = []
for s in png_sizes:
    out = square_img.resize((s, s), Image.LANCZOS)
    p = os.path.join(icons_dir, f"icon-{s}x{s}.png")
    out.save(p, format="PNG")
    png_paths.append(p)

# Generate favicon.ico (multiple sizes inside)
ico_sizes = [16, 32, 48, 64]
ico_images = [square_img.resize((s, s), Image.LANCZOS) for s in ico_sizes]
ico_path = os.path.join(static_dir, "favicon.ico")
ico_images[0].save(ico_path, format="ICO", sizes=[(s, s) for s in ico_sizes])

# Copy original to static root as well
static_src = os.path.join(static_dir, "caiyun_icon.jpg")
if not os.path.exists(static_src):
    img.convert("RGB").save(static_src, format="JPEG")

print("Generated icons:")
print(" -", ico_path)
for p in png_paths:
    print(" -", p)
print("Copied source to", static_src)
