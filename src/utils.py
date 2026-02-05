import ffmpeg
import cv2
import numpy as np
import os
from PIL import Image, ImageDraw, ImageFont

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

def render_caption_frame(frame, text_lines, width, height, font):
    """
    Draws specific text lines on a CV2 frame using PIL.
    """
    # convert CV2 (BGR) to PIL (RGB)
    pil_img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(pil_img)

    # style settings
    text_color = (255, 255, 255)
    bg_color = (0, 0, 0, 160)
    
    # bottom 25% of the screen
    start_y_pos = int(height * 0.75)
    
    for i, line in enumerate(text_lines):
        text = line['text']
        
        # calculate text size
        bbox = draw.textbbox((0, 0), text, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        
        # center x
        x_pos = (width - text_w) // 2
        # offset y for multiple lines
        y_pos = start_y_pos + (i * (text_h + 30))
        
        # draw background pill
        padding = 15
        draw.rounded_rectangle(
            [x_pos - padding, y_pos - padding, x_pos + text_w + padding, y_pos + text_h + padding],
            radius=10,
            fill=bg_color
        )
        
        # draw Text
        draw.text((x_pos, y_pos), text, font=font, fill=text_color)

    # convert back to CV2 (BGR)
    return cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)

def burn_captions_to_video(input_path, output_path, captions):
    """
    Reads video frame-by-frame, draws captions, and saves output.
    Uses a temp file for video, then merges original audio back.
    """
    base, _ = os.path.splitext(output_path)
    temp_video = f"{base}_temp_video.mp4"

    cap = cv2.VideoCapture(input_path)
    if not cap.isOpened():
        raise Exception("Could not open video file.")

    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    fourcc = cv2.VideoWriter.fourcc(*'mp4v')
    out = cv2.VideoWriter(temp_video, fourcc, fps, (width, height))

    # font loading
    try:
        font = ImageFont.truetype("Arial.ttf", size=int(height/35)) 
    except:
        font = ImageFont.load_default()

    frame_idx = 0
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
            
        current_time = frame_idx / fps
        
        # find active captions for this timestamp
        active_lines = [c for c in captions if c['start'] <= current_time <= c['end']]
        
        if active_lines:
            frame = render_caption_frame(frame, active_lines, width, height, font)
            
        out.write(frame)
        frame_idx += 1
        
    cap.release()
    out.release()
    
    # merge audio
    try:
        probe = ffmpeg.probe(input_path)
        has_audio = any(s['codec_type'] == 'audio' for s in probe['streams'])
        
        v_stream = ffmpeg.input(temp_video)
        
        if has_audio:
            a_stream = ffmpeg.input(input_path).audio
            ffmpeg.output(v_stream, a_stream, output_path).overwrite_output().run(quiet=True)
        else:
            ffmpeg.output(v_stream, output_path).overwrite_output().run(quiet=True)
            
    finally:
        if os.path.exists(temp_video):
            os.remove(temp_video)