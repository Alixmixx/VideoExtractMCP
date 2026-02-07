import ffmpeg
import os

def validate_file_exists(path):
    """Raise ValueError if file does not exist."""
    if not os.path.exists(path):
        raise ValueError(f"File not found: {path}")

def get_video_duration(path):
    """Return video duration in seconds via ffprobe."""
    probe = ffmpeg.probe(path)
    return float(probe['format']['duration'])

def validate_time_range(start, end, duration=None):
    """Raise ValueError if the time range is invalid."""
    if start < 0:
        raise ValueError(f"start_time ({start}) must be >= 0")
    if end <= start:
        raise ValueError(f"end_time ({end}) must be greater than start_time ({start})")
    if duration is not None and end > duration:
        raise ValueError(f"end_time ({end}) exceeds video duration ({duration:.2f}s)")

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

def build_crossfade_concat(file_path, segments, transition_duration=0.5):
    """
    Concatenate segments with xfade (video) and acrossfade (audio) transitions.
    Chains iteratively: xfade(seg1, seg2) -> xfade(result, seg3) -> ...
    Returns (video_stream, audio_stream).
    """
    clips_v = []
    clips_a = []
    durations = []
    for start, end in segments:
        clip = ffmpeg.input(file_path, ss=start, to=end)
        clips_v.append(clip.video)
        clips_a.append(clip.audio)
        durations.append(end - start)

    # start with first segment
    video = clips_v[0]
    audio = clips_a[0]
    # cumulative offset tracks where each xfade happens
    cumulative = durations[0]

    for i in range(1, len(clips_v)):
        offset = cumulative - transition_duration
        video = ffmpeg.filter([video, clips_v[i]], 'xfade',
                              transition='fade', duration=transition_duration, offset=offset)
        audio = ffmpeg.filter([audio, clips_a[i]], 'acrossfade',
                              d=transition_duration)
        # each xfade shortens total by transition_duration
        cumulative += durations[i] - transition_duration

    return video, audio

def apply_fade_in_out(video, audio, total_duration, fade_duration=0.5):
    """
    Apply fade-in at start and fade-out at end on both video and audio.
    """
    fade_out_start = max(0, total_duration - fade_duration)
    video = video.filter('fade', type='in', duration=fade_duration)
    video = video.filter('fade', type='out', start_time=fade_out_start, duration=fade_duration)
    audio = audio.filter('afade', type='in', duration=fade_duration)
    audio = audio.filter('afade', type='out', start_time=fade_out_start, duration=fade_duration)
    return video, audio

def _escape_drawtext(text):
    """Escape special characters for FFmpeg drawtext filter."""
    text = text.replace("\\", "\\\\")
    text = text.replace(":", "\\:")
    text = text.replace("'", "\u2019")
    return text

def build_drawtext_filters(stream, captions, video_width, video_height, caption_style=None):
    """
    Chains drawtext filters for each caption with word-wrapping and
    optional per-word karaoke highlighting.

    Uses a 3-layer approach per caption:
      Layer 1 — background box via invisible drawtext (FFmpeg-centered)
      Layer 2 — highlight rectangles via drawbox (estimated positions, karaoke only)
      Layer 3 — visible text via drawtext (FFmpeg-centered)

    caption_style keys (all optional):
      font_size:       int, overrides auto-calculated size
      font_color:      str, text color (default 'white')
      highlight_color: str, karaoke highlight box color (default '#FFE2A5@0.86')
      bg_color:        str, background box color (default 'black@0.6')
      position:        str, 'top', 'center', or 'bottom' (default 'bottom')
      karaoke:         bool, enable per-word highlighting (default True)
    """
    if not captions:
        return stream

    style = caption_style or {}
    font_size = style.get('font_size', max(16, int(video_height / 35)))
    font_color = style.get('font_color', 'white')
    highlight_color = style.get('highlight_color', '#FFE2A5@0.86')
    bg_color = style.get('bg_color', 'black@0.6')
    position = style.get('position', 'bottom')
    karaoke = style.get('karaoke', True)

    avg_char_w = font_size * 0.55
    space_w = font_size * 0.28
    line_height = int(font_size * 1.6)
    box_pad = 10
    highlight_pad = 5
    text_h_est = int(font_size * 1.15)
    max_text_w = video_width - 60

    # vertical position
    if position == 'top':
        y_anchor = int(video_height * 0.08)
    elif position == 'center':
        y_anchor = int(video_height * 0.45)
    else:
        y_anchor = int(video_height * 0.75)

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

        # --- LAYER 1: background boxes (invisible text, FFmpeg-centered) ---
        for li, line_words in enumerate(lines):
            line_text = ' '.join(line_words)
            y = y_anchor + li * line_height
            escaped_line = _escape_drawtext(line_text)

            stream = stream.filter(
                'drawtext',
                text=escaped_line,
                fontsize=font_size,
                fontcolor=f'{font_color}@0',
                box=1,
                boxcolor=bg_color,
                boxborderw=box_pad,
                x='(w-text_w)/2',
                y=str(y),
                enable=f'between(t,{start},{end})'
            )

        # --- LAYER 2: highlight boxes (karaoke mode only) ---
        if karaoke and total_words > 0 and duration > 0:
            word_idx = 0
            for li, line_words in enumerate(lines):
                y = y_anchor + li * line_height
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
                        color=highlight_color,
                        t='fill',
                        enable=f'between(t,{ws},{we})'
                    )

                    cur_x += word_w + space_w
                    word_idx += 1

        # --- LAYER 3: visible text (FFmpeg-centered, on top) ---
        for li, line_words in enumerate(lines):
            line_text = ' '.join(line_words)
            y = y_anchor + li * line_height
            escaped_line = _escape_drawtext(line_text)

            stream = stream.filter(
                'drawtext',
                text=escaped_line,
                fontsize=font_size,
                fontcolor=font_color,
                borderw=2,
                bordercolor='black',
                x='(w-text_w)/2',
                y=str(y),
                enable=f'between(t,{start},{end})'
            )

    return stream
