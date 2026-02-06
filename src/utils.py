import ffmpeg

def create_blurred_background_filter(stream, width=1080, height=1920):
    """
    FFmpeg filter graph: creates a 9:16 background from a 16:9 video
    by cropping, blurring, and overlaying the original.
    """
    # plit the stream, one for background (blurred), one for foreground
    split = stream.split()
    bg = split[0]
    fg = split[1]

    # background: ccale to cover, crop to exact 9:16, heavy blur
    bg = (
        bg
        .filter('scale', w=width, h=height, force_original_aspect_ratio="increase")
        .filter('crop', w=width, h=height)
        .filter('boxblur', luma_radius=20, luma_power=2)
    )

    # foreground: Scale to fit width, keep aspect ratio
    fg = fg.filter('scale', w=width, h=-1)

    # overlay FG centered on BG
    return ffmpeg.overlay(bg, fg, x="(W-w)/2", y="(H-h)/2")

def get_format_dimensions(output_format, custom_ratio=None):
    """
    Return (width, height) for the given output format.
    Supports 'original', 'short' (9:16), 'square' (1:1), 'custom' with a ratio string like "4:5".
    Returns None for 'original' (no resize needed).
    """
    if output_format == 'original':
        return None
    if output_format == 'short':
        return (1080, 1920)
    if output_format == 'square':
        return (1080, 1080)
    if output_format == 'custom' and custom_ratio:
        parts = custom_ratio.split(':')
        if len(parts) != 2:
            raise ValueError(f"Invalid ratio format '{custom_ratio}', expected 'W:H' e.g. '4:5'")
        rw, rh = int(parts[0]), int(parts[1])
        # scale so the larger dimension is 1080
        if rw >= rh:
            w = 1080
            h = int(1080 * rh / rw)
        else:
            h = 1920
            w = int(1920 * rw / rh)
        # ensure even dimensions for codec compatibility
        return (w - w % 2, h - h % 2)
    return None

def _escape_drawtext(text):
    """Escape special characters for FFmpeg drawtext filter."""
    text = text.replace("\\", "\\\\")
    text = text.replace(":", "\\:")
    text = text.replace("'", "\u2019")
    return text

def build_drawtext_filters(stream, captions, video_width, video_height):
    """
    Chains drawtext filters for each caption with word-wrapping and
    per-word karaoke highlighting (active word gets a gold background).

    Uses a 3-layer approach per caption:
      Layer 1 — dark background box via invisible drawtext (FFmpeg-centered)
      Layer 2 — gold highlight rectangles via drawbox (estimated positions)
      Layer 3 — visible white text via drawtext (FFmpeg-centered)
    Text is always perfectly centered; only the highlight boxes use estimates.
    """
    if not captions:
        return stream

    font_size = max(16, int(video_height / 35))
    avg_char_w = font_size * 0.55
    space_w = font_size * 0.28
    line_height = int(font_size * 1.6)
    box_pad = 10
    highlight_pad = 5
    text_h_est = int(font_size * 1.15)
    max_text_w = video_width - 60

    for caption in captions:
        text = caption['text'].strip()
        start = caption['start']
        end = caption['end']
        words = text.split()
        if not words:
            continue

        # word-wrap into lines
        lines = []
        current_line = []
        current_w = 0.0
        for word in words:
            word_w = len(word) * avg_char_w
            needed = word_w + (space_w if current_line else 0)
            if current_w + needed > max_text_w and current_line:
                lines.append(current_line[:])
                current_line = [word]
                current_w = word_w
            else:
                current_line.append(word)
                current_w += needed
        if current_line:
            lines.append(current_line)

        total_words = len(words)
        duration = end - start
        base_y = int(video_height * 0.75)

        # --- LAYER 1: dark background boxes (invisible text, FFmpeg-centered) ---
        for li, line_words in enumerate(lines):
            line_text = ' '.join(line_words)
            y = base_y + li * line_height
            escaped_line = _escape_drawtext(line_text)

            stream = stream.filter(
                'drawtext',
                text=escaped_line,
                fontsize=font_size,
                fontcolor='white@0',
                box=1,
                boxcolor='black@0.6',
                boxborderw=box_pad,
                x='(w-text_w)/2',
                y=str(y),
                enable=f'between(t,{start},{end})'
            )

        # --- LAYER 2: gold highlight boxes (drawbox at estimated positions) ---
        word_idx = 0
        for li, line_words in enumerate(lines):
            y = base_y + li * line_height
            line_w = sum(len(w) * avg_char_w for w in line_words) + max(0, len(line_words) - 1) * space_w
            line_x = max(box_pad, int((video_width - line_w) / 2))

            cur_x = float(line_x)
            for word in line_words:
                word_w = len(word) * avg_char_w
                ws = start + (word_idx / total_words) * duration
                we = start + ((word_idx + 1) / total_words) * duration

                stream = stream.filter(
                    'drawbox',
                    x=int(cur_x - highlight_pad),
                    y=int(y - highlight_pad),
                    width=int(word_w + 2 * highlight_pad),
                    height=int(text_h_est + 2 * highlight_pad),
                    color='#FFE2A5@0.86',
                    t='fill',
                    enable=f'between(t,{ws},{we})'
                )

                cur_x += word_w + space_w
                word_idx += 1

        # --- LAYER 3: visible white text (FFmpeg-centered, on top) ---
        for li, line_words in enumerate(lines):
            line_text = ' '.join(line_words)
            y = base_y + li * line_height
            escaped_line = _escape_drawtext(line_text)

            stream = stream.filter(
                'drawtext',
                text=escaped_line,
                fontsize=font_size,
                fontcolor='white',
                borderw=2,
                bordercolor='black',
                x='(w-text_w)/2',
                y=str(y),
                enable=f'between(t,{start},{end})'
            )

    return stream
