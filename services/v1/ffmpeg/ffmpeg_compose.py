# Copyright (c) 2025 Stephen G. Pope
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.



import os
import subprocess
import json
import re
from services.file_management import download_file
from config import LOCAL_STORAGE_PATH
import shlex         # ZN: нужно для безопасных вызовов ffprobe
import textwrap      # ZN: для автоматического переноса строк

def get_extension_from_format(format_name):
    # Mapping of common format names to file extensions
    format_to_extension = {
        'mp4': 'mp4',
        'mov': 'mov',
        'avi': 'avi',
        'mkv': 'mkv',
        'webm': 'webm',
        'gif': 'gif',
        'apng': 'apng',
        'jpg': 'jpg',
        'jpeg': 'jpg',
        'png': 'png',
        'image2': 'png',  # Assume png for image2 format
        'rawvideo': 'raw',
        'mp3': 'mp3',
        'wav': 'wav',
        'aac': 'aac',
        'flac': 'flac',
        'ogg': 'ogg'
    }
    return format_to_extension.get(format_name.lower(), 'mp4')  # Default to mp4 if unknown

def get_metadata(filename, metadata_requests, job_id):
    metadata = {}
    if metadata_requests.get('thumbnail'):
        thumbnail_filename = f"{os.path.splitext(filename)[0]}_thumbnail.jpg"
        thumbnail_command = [
            'ffmpeg',
            '-i', filename,
            '-vf', 'select=eq(n\,0)',
            '-vframes', '1',
            thumbnail_filename
        ]
        try:
            subprocess.run(thumbnail_command, check=True, capture_output=True, text=True)
            if os.path.exists(thumbnail_filename):
                metadata['thumbnail'] = thumbnail_filename  # Return local path instead of URL
        except subprocess.CalledProcessError as e:
            print(f"Thumbnail generation failed: {e.stderr}")

    if metadata_requests.get('filesize'):
        metadata['filesize'] = os.path.getsize(filename)

    if metadata_requests.get('encoder') or metadata_requests.get('duration') or metadata_requests.get('bitrate'):
        ffprobe_command = [
            'ffprobe',
            '-v', 'quiet',
            '-print_format', 'json',
            '-show_format',
            '-show_streams',
            filename
        ]
        result = subprocess.run(ffprobe_command, capture_output=True, text=True)
        probe_data = json.loads(result.stdout)
        
        if metadata_requests.get('duration'):
            metadata['duration'] = float(probe_data['format']['duration'])
        if metadata_requests.get('bitrate'):
            metadata['bitrate'] = int(probe_data['format']['bit_rate'])
        
        if metadata_requests.get('encoder'):
            metadata['encoder'] = {}
            for stream in probe_data['streams']:
                if stream['codec_type'] == 'video':
                    metadata['encoder']['video'] = stream.get('codec_name', 'unknown')
                elif stream['codec_type'] == 'audio':
                    metadata['encoder']['audio'] = stream.get('codec_name', 'unknown')

    return metadata

# ZN: ───────────────────────────────────────────────────────────────────────────────
# ZN: Авто-текстовая логика (аналог /v1/video/caption)
# ZN: ───────────────────────────────────────────────────────────────────────────────

def ffprobe_get_size(path: str):
    """ZN: Возвращает (width, height) видеофайла через ffprobe."""
    cmd = f"ffprobe -v error -select_streams v:0 -show_entries stream=width,height -of json {shlex.quote(path)}"
    p = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if p.returncode != 0:
        return (720, 1280)  # ZN: дефолт 9:16
    try:
        info = json.loads(p.stdout)
        s = info["streams"][0]
        return int(s.get("width", 720)), int(s.get("height", 1280))
    except Exception:
        return (720, 1280)

def wrap_text_to_width(text: str, max_px: int, fontsize: int) -> str:
    """ZN: Перенос строк с учётом примерной ширины символа (~0.6*fontsize)."""
    avg_px_per_char = max(1, int(fontsize * 0.6))
    max_chars = max(8, int(max_px / avg_px_per_char))
    wrapped = textwrap.fill(text, width=max_chars, break_long_words=False, break_on_hyphens=False)
    return wrapped.replace("\n", r"\n")

def build_autotext_drawtext(
    text: str,
    width: int,
    height: int,
    fontfile: str = "/data/fonts/DejaVuSans-Bold.ttf",
    fontcolor: str = "white",
    base_fontsize_pct: float = 0.05,
    position: str = "center",
    offset_y: int = 0,
    box: bool = True,
    boxcolor: str = "black@0.5",
    boxborderw: int = 20,
):
    """ZN: Формирует drawtext с авторазмером, центровкой и переносом строк."""
    fontsize = max(24, int(height * base_fontsize_pct))         # ZN: масштаб по высоте видео
    max_text_width = int(width * 0.9)                           # ZN: максимум 90% ширины кадра
    safe_text = text.replace("'", r"\'")                        # ZN: экранируем одинарные кавычки
    wrapped = wrap_text_to_width(safe_text, max_text_width, fontsize)
    x_expr = "(w-text_w)/2"                                     # ZN: по центру горизонтали

    # ZN: позиционирование по вертикали
    if position == "top":
        y_expr = f"{fontsize*2}+{offset_y}"
    elif position == "bottom":
        y_expr = f"(h-text_h-{fontsize*2})+{offset_y}"
    else:
        y_expr = f"(h-text_h)/2+{offset_y}"

    box_bit = "1" if box else "0"
    draw = (
        f"drawtext=fontfile={fontfile}:"
        f"text='{wrapped}':"
        f"fontcolor={fontcolor}:"
        f"fontsize={fontsize}:"
        f"x={x_expr}:y={y_expr}:"
        f"box={box_bit}:boxcolor={boxcolor}:boxborderw={boxborderw}"
    )
    return draw
# ZN: ───────────────────────────────────────────────────────────────────────────────


def process_ffmpeg_compose(data, job_id):
    output_filenames = []
    
    # Build FFmpeg command
    command = ["ffmpeg"]
    
    # Add global options
    for option in data.get("global_options", []):
        command.append(option["option"])
        if "argument" in option and option["argument"] is not None:
            command.append(str(option["argument"]))
    
    # Add inputs
    input_paths = []
    for input_data in data["inputs"]:
        if "options" in input_data:
            for option in input_data["options"]:
                command.append(option["option"])
                if "argument" in option and option["argument"] is not None:
                    command.append(str(option["argument"]))
        input_path = download_file(input_data["file_url"], LOCAL_STORAGE_PATH)
        input_paths.append(input_path)
        command.extend(["-i", input_path])
    
    # Add filters
#    subtitles_paths = []  # Track downloaded subtitles/filter files
#    if data.get("filters"):
#        new_filters = []
#        for filter_obj in data["filters"]:
#            filter_str = filter_obj["filter"]

    # Add filters
    subtitles_paths = []  # Track downloaded subtitles/filter files
    if data.get("filters"):
        new_filters = []
        for filter_obj in data["filters"]:
            # ZN: ────────────────────────────────────────────────
            # ZN: Новый режим — auto-text (как /v1/video/caption)
            # ZN: Если в JSON есть "autotext": true, применяем автоформатирование
            # ZN: ────────────────────────────────────────────────
            if filter_obj.get("autotext"):
                text = filter_obj.get("text", "")
                fontfile = filter_obj.get("fontfile", "/data/fonts/DejaVuSans-Bold.ttf")
                fontcolor = filter_obj.get("fontcolor", "white")
                position = filter_obj.get("position", "center")       # top|center|bottom
                offset_y = int(filter_obj.get("offset_y", 0))
                base_pct = float(filter_obj.get("base_fontsize_pct", 0.05))
                box = bool(filter_obj.get("box", True))
                boxcolor = filter_obj.get("boxcolor", "black@0.5")
                boxborderw = int(filter_obj.get("boxborderw", 20))
    
                # ZN: Определяем размер видео (берём первый input)
                try:
                    w, h = ffprobe_get_size(input_paths[0])
                except Exception:
                    w, h = (720, 1280)
    
                # ZN: Создаём фильтр с авто-параметрами
                draw = build_autotext_drawtext(
                    text=text, width=w, height=h,
                    fontfile=fontfile, fontcolor=fontcolor,
                    base_fontsize_pct=base_pct, position=position,
                    offset_y=offset_y, box=box,
                    boxcolor=boxcolor, boxborderw=boxborderw
                )
                new_filters.append(draw)
                continue
            # ZN: ────────────────────────────────────────────────
    
            # ZN: Обычная логика (как была)
            filter_str = filter_obj["filter"]
            def replace_subtitles_url(match):
                url = match.group(1)
                local_path = download_file(url, LOCAL_STORAGE_PATH)
                subtitles_paths.append(local_path)
                fixed_path = local_path.replace('\\', '/')
                return f"subtitles='{fixed_path}"
            filter_str = re.sub(r"subtitles=['\"]([^'\"]+)", replace_subtitles_url, filter_str)
            new_filters.append(filter_str)
    
        filter_complex = ";".join(new_filters)
        command.extend(["-filter_complex", filter_complex])


#            def replace_subtitles_url(match):
#                url = match.group(1)
#                local_path = download_file(url, LOCAL_STORAGE_PATH)
#                subtitles_paths.append(local_path)
#                fixed_path = local_path.replace('\\', '/')
#                return f"subtitles='{fixed_path}"  # keep the opening quote
#            # Regex: subtitles='<url>' or subtitles="<url>"
#            filter_str = re.sub(r"subtitles=['\"]([^'\"]+)", replace_subtitles_url, filter_str)
#            new_filters.append(filter_str)
#        filter_complex = ";".join(new_filters)
#        command.extend(["-filter_complex", filter_complex])
    
    # Add outputs
    for i, output in enumerate(data["outputs"]):
        format_name = None
        for option in output["options"]:
            if option["option"] == "-f":
                format_name = option.get("argument")
                break
        
        extension = get_extension_from_format(format_name) if format_name else 'mp4'
        output_filename = os.path.join(LOCAL_STORAGE_PATH, f"{job_id}_output_{i}.{extension}")
        output_filenames.append(output_filename)
        
        for option in output["options"]:
            command.append(option["option"])
            if "argument" in option and option["argument"] is not None:
                command.append(str(option["argument"]))
        command.append(output_filename)
    
    # Execute FFmpeg command
    try:
        subprocess.run(command, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        raise Exception(f"FFmpeg command failed: {e.stderr}")
    
    # Clean up input files
    for input_path in input_paths:
        if os.path.exists(input_path):
            os.remove(input_path)
    # Clean up subtitles/filter files
    for subtitles_path in subtitles_paths:
        if os.path.exists(subtitles_path):
            os.remove(subtitles_path)
    # Get metadata if requested
    metadata = []
    if data.get("metadata"):
        for output_filename in output_filenames:
            metadata.append(get_metadata(output_filename, data["metadata"], job_id))
    
    return output_filenames, metadata
