from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def _font(size, bold=False):
    candidates = [
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/calibrib.ttf" if bold else "C:/Windows/Fonts/calibri.ttf",
    ]
    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _center(draw, box, text, font, fill):
    bbox = draw.textbbox((0, 0), text, font=font)
    x = box[0] + (box[2] - box[0] - (bbox[2] - bbox[0])) / 2
    y = box[1] + (box[3] - box[1] - (bbox[3] - bbox[1])) / 2
    draw.text((x, y), text, font=font, fill=fill)


def save_confusion_matrix_png(matrix, output_path):
    """Render a heatmap-style confusion matrix image for README/reporting."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    tn = int(matrix.loc["Actual 0", "Predicted 0"])
    fp = int(matrix.loc["Actual 0", "Predicted 1"])
    fn = int(matrix.loc["Actual 1", "Predicted 0"])
    tp = int(matrix.loc["Actual 1", "Predicted 1"])

    values = [[tn, fp], [fn, tp]]
    max_value = max(tn, fp, fn, tp, 1)

    img = Image.new("RGB", (860, 720), "#FFFFFF")
    draw = ImageDraw.Draw(img)
    title_font = _font(28)
    axis_font = _font(21)
    tick_font = _font(18)
    value_font = _font(21)
    small_font = _font(16)

    def blue_scale(value):
        ratio = value / max_value
        low = (239, 246, 255)
        high = (8, 64, 129)
        return tuple(int(low[i] + (high[i] - low[i]) * ratio) for i in range(3))

    _center(draw, (0, 28, 860, 70), "Confusion Matrix", title_font, "#1F2937")

    grid_left, grid_top = 170, 180
    cell = 190
    grid_right = grid_left + cell * 2
    grid_bottom = grid_top + cell * 2

    _center(draw, (grid_left, 88, grid_right, 125), "Prediction", axis_font, "#111827")
    _center(draw, (grid_left, 126, grid_left + cell, 165), "No Churn", tick_font, "#111827")
    _center(draw, (grid_left + cell, 126, grid_right, 165), "Churn", tick_font, "#111827")

    draw.text((34, grid_top + 140), "Actual", font=axis_font, fill="#111827")
    _center(draw, (55, grid_top, grid_left - 20, grid_top + cell), "No Churn", tick_font, "#111827")
    _center(draw, (55, grid_top + cell, grid_left - 20, grid_bottom), "Churn", tick_font, "#111827")

    for r in range(2):
        for c in range(2):
            value = values[r][c]
            x0 = grid_left + c * cell
            y0 = grid_top + r * cell
            fill = blue_scale(value)
            draw.rectangle((x0, y0, x0 + cell, y0 + cell), fill=fill, outline="#111827", width=1)
            text_fill = "#FFFFFF" if value / max_value > 0.45 else "#0F172A"
            _center(draw, (x0, y0, x0 + cell, y0 + cell), f"{value:,}", value_font, text_fill)

    draw.rectangle((grid_left, grid_top, grid_right, grid_bottom), outline="#111827", width=2)

    bar_left, bar_top, bar_w, bar_h = grid_right + 45, grid_top, 22, cell * 2
    for y in range(bar_h):
        value = max_value * (1 - y / max(bar_h - 1, 1))
        draw.line(
            (bar_left, bar_top + y, bar_left + bar_w, bar_top + y),
            fill=blue_scale(value),
        )
    draw.rectangle((bar_left, bar_top, bar_left + bar_w, bar_top + bar_h), outline="#111827", width=1)

    for i in range(6):
        y = bar_top + bar_h - i * (bar_h / 5)
        tick_value = int(max_value * i / 5)
        draw.line((bar_left + bar_w, y, bar_left + bar_w + 8, y), fill="#111827", width=1)
        draw.text((bar_left + bar_w + 14, y - 10), f"{tick_value:,}", font=small_font, fill="#111827")

    img.save(output_path)
    return output_path
