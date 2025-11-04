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

# ZN: перенос текста по ширине видео с учётом размера шрифта
import math
# ZN: перенос текста по ширине видео с учётом размера шрифта

from services.file_management import download_file
from config import LOCAL_STORAGE_PATH

# ZN: добавляем поддержку переноса строк
def wrap_text_to_fit_width(text: str, video_width: int, fontsize: int = 64) -> str:
    """
    ZN: Делит текст на строки с учётом ширины видео и размера шрифта.
    Средняя ширина символа ≈ 0.6 * fontsize.
    """
    if not text:
        return text

    # Примерная ширина символа
    avg_px_per_char = fontsize * 0.6

    # Сколько символов помещается в одну строку (оставим 90% ширины для отступов)
    max_chars = int((video_width * 0.9) / avg_px_per_char)

    # Перенос строк
    import textwrap
    wrapped = textwrap.fill(
        text,
        width=max_chars,
        break_long_words=False,
        break_on_hyphens=False
    )

    # Для ffmpeg нужны \n, а не реальные переводы
    return wrapped.replace("\n", r"\n")
# ZN: добавляем поддержку переноса строк

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
    subtitles_paths = []  # Track downloaded subtitles/filter files
    if data.get("filters"):
        new_filters = []
#        for filter_obj in data["filters"]:
#            filter_str = filter_obj["filter"]
#            def replace_subtitles_url(match):
#                url = match.group(1)
#                local_path = download_file(url, LOCAL_STORAGE_PATH)
#                subtitles_paths.append(local_path)
#                fixed_path = local_path.replace('\\', '/')
#                return f"subtitles='{fixed_path}"  # keep the opening quote
#            # Regex: subtitles='<url>' or subtitles="<url>"
#            filter_str = re.sub(r"subtitles=['\"]([^'\"]+)", replace_subtitles_url, filter_str)
#            new_filters.append(filter_str)

# ZN: добавляем поддержку переноса строк
        for filter_obj in data["filters"]:
            filter_str = filter_obj["filter"]
        
            # ZN: Если в фильтре присутствует "text=" — применим авторазбиение по строкам
            if "text=" in filter_str:
                try:
                    # ZN: Ищем текст в кавычках
                    match = re.search(r"text='([^']*)'", filter_str)
                    if match:
                        raw_text = match.group(1)
                        # ZN: Берём параметр max_words_per_line (по умолчанию 6)
                        max_words = int(filter_obj.get("max_words_per_line", 6))
                        wrapped = wrap_text_by_words(raw_text, max_words)
                        # ZN: Заменяем текст внутри фильтра на разбитый по строкам
                        filter_str = re.sub(r"text='[^']*'", f"text='{wrapped}'", filter_str)
                except Exception as e:
                    print(f"[WARN] text wrapping failed: {e}")
        
            def replace_subtitles_url(match):
                url = match.group(1)
                local_path = download_file(url, LOCAL_STORAGE_PATH)
                subtitles_paths.append(local_path)
                fixed_path = local_path.replace('\\', '/')
                return f"subtitles='{fixed_path}"  # keep the opening quote
        
            filter_str = re.sub(r"subtitles=['\"]([^'\"]+)", replace_subtitles_url, filter_str)
            new_filters.append(filter_str)
# ZN: добавляем поддержку переноса строк
        
        filter_complex = ";".join(new_filters)
        command.extend(["-filter_complex", filter_complex])
    
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
