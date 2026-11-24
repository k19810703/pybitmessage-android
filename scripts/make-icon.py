#!/usr/bin/env python3
"""Build the Android launcher icon from the source artwork (M5.1.1).

    python3 scripts/make-icon.py             # writes src/images/icon.png
    python3 scripts/make-icon.py --preview   # also writes /tmp/icon-preview-*.png

Source: ``image_20261123_211538_610565.jpeg`` (2048x2048) -- a dark navy
"secure messaging" emblem: shield + "SJY" + padlock + speech bubble, with
hairline circuit traces behind it.

What is changed, and why
------------------------
A straight downscale of the artwork makes a near-black tile: mean luminance is
35/255, and at 48-96 dp the letters and the lock disappear into the
background. Four adjustments turn it into a usable icon while keeping the
design intact:

1. **crop** to the emblem so it fills ~79 % of the canvas (Android masks the
   outer edge, and adaptive icons only guarantee the inner 66 %).
2. **lift the highlights** (brightness + a bloom on the bright pixels) so the
   shield rim, the padlock and the bubble stay separated from the background
   after downscaling.
3. **flatten the background** to a flat navy with a soft blue glow: the traces
   are what turn to mud at small sizes, and the emblem is what must read.
4. slight contrast/saturation bump.

The result is opaque RGB -- a full-bleed square, the safest thing to hand to
any launcher mask (some launchers apply a squircle, some a circle, some none).
"""
import argparse
import os

from PIL import Image, ImageChops, ImageEnhance, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
SOURCE = os.path.join(REPO, 'image_20261123_211538_610565.jpeg')
OUTPUT = os.path.join(REPO, 'PyBitmessage', 'src', 'images', 'icon.png')

#: Crop box in source pixels (left, upper, right, lower). Measured, not
#: guessed: blurring the artwork with a 12 px Gaussian kills the hairline
#: traces and thresholding the result gives the emblem extent in the
#: 2048x2048 original -- x 327..1711, y 418..1633 (1375x1210, centred near
#: 1017,1025). A 1750 px square around that centre makes the emblem fill ~79 %
#: of the canvas.
CROP = (142, 150, 1892, 1900)
SIZE = 512

#: Tuned by eye against 48/96/192 dp previews; see the docstring.
BRIGHTNESS = 1.50
BLOOM_THRESHOLD = 70
BLOOM_GAIN = 1.20
BLOOM_RADIUS = 6
CONTRAST = 1.12
SATURATION = 1.20
#: Where the artwork stays and where the flat background takes over, as radii
#: in output pixels.
KEEP_INNER = 180
FADE_OUTER = 262
BACKGROUND = (9, 18, 32)
BACKGROUND_GLOW = (22, 50, 92)


def radial_mask(size, inner, outer):
    """255 at radius <= inner, 0 at radius >= outer, smooth in between.

    Built from ``Image.radial_gradient`` on purpose. Doing it with
    ``ImageDraw.ellipse`` loops is a trap: ``ellipse`` fills the *whole* disc,
    so every larger (dimmer) ring paints over the centre and the "gradient"
    ends up uniformly the outermost alpha -- which is exactly how the first
    version of this script produced a blank icon.
    """
    gradient = Image.radial_gradient('L').resize((size, size), Image.BICUBIC)
    # radial_gradient: 0 in the centre, 255 at the edge -> scale to our radii
    lo = int(inner / (size / 2.0) * 255)
    hi = max(lo + 1, int(outer / (size / 2.0) * 255))
    lut = []
    for value in range(256):
        if value <= lo:
            lut.append(255)
        elif value >= hi:
            lut.append(0)
        else:
            lut.append(int(255 * (1 - (value - lo) / float(hi - lo))))
    return gradient.point(lut)


def _bloom(image, threshold, radius, gain):
    """Screen a blurred copy of the bright pixels back over the image."""
    lut = [0 if i < threshold else min(255, int((i - threshold) * gain))
           for i in range(256)]
    bright = image.point(lut * 3).filter(ImageFilter.GaussianBlur(radius))
    return ImageChops.screen(image, bright)


def _flat_background(size):
    glow = Image.new('RGB', (size, size), BACKGROUND_GLOW)
    base = Image.new('RGB', (size, size), BACKGROUND)
    return Image.composite(glow, base, radial_mask(size, 30, 260))


def build():
    if not os.path.exists(SOURCE):
        raise SystemExit('source artwork missing: %s' % SOURCE)

    emblem = Image.open(SOURCE).convert('RGB').crop(CROP)
    emblem = emblem.resize((SIZE, SIZE), Image.LANCZOS)

    emblem = ImageEnhance.Brightness(emblem).enhance(BRIGHTNESS)
    emblem = _bloom(emblem, BLOOM_THRESHOLD, BLOOM_RADIUS, BLOOM_GAIN)
    emblem = ImageEnhance.Color(emblem).enhance(SATURATION)
    emblem = ImageEnhance.Contrast(emblem).enhance(CONTRAST)

    icon = Image.composite(
        emblem, _flat_background(SIZE), radial_mask(SIZE, KEEP_INNER,
                                                    FADE_OUTER))
    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    icon.save(OUTPUT, 'PNG', optimize=True)
    return icon


def preview(icon):
    """Write the sizes a launcher actually uses, for eyeballing."""
    written = []
    for size in (48, 72, 96, 144, 192, 512):
        path = '/tmp/icon-preview-%d.png' % size
        icon.resize((size, size), Image.LANCZOS).save(path)
        written.append(path)
    # 48 px magnified with NEAREST is how small-size mush shows up
    zoom = icon.resize((48, 48), Image.LANCZOS).resize((384, 384), Image.NEAREST)
    path = '/tmp/icon-preview-48-zoom.png'
    zoom.save(path)
    written.append(path)
    return written


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--preview', action='store_true')
    args = parser.parse_args()

    icon = build()
    print('wrote %s (%dx%d, %d bytes)' % (
        OUTPUT, icon.width, icon.height, os.path.getsize(OUTPUT)))
    if args.preview:
        for path in preview(icon):
            print('preview', path)


if __name__ == '__main__':
    main()
