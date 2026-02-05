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
