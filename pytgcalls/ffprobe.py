import asyncio
import json
import subprocess
from json import JSONDecodeError
from typing import Dict, List, Optional, Tuple, Union

from .exceptions import (
    FFmpegNotInstalled,
    InvalidVideoProportion,
    NoAudioSourceFound,
    NoVideoSourceFound,
)
from .types.input_stream.video_tools import check_support


class FFprobe:
    @staticmethod
    def ffmpeg_headers(
        headers: Optional[Dict[str, str]] = None,
    ) -> str:
        if not headers:
            return ""
        built_header = "".join(f"{k}: {v}\r\n" for k, v in headers.items())
        return ":_cmd_:".join(["-headers", built_header])

    @staticmethod
    async def check_file(
        path: str,
        needed_audio: bool = False,
        needed_video: bool = False,
        needed_image: bool = False,
        headers: Optional[Dict[str, str]] = None,
    ) -> Union[Tuple[int, int, bool], bool, None]:
        ffmpeg_params: List[str] = []
        have_header = False

        if headers and check_support(path):
            built_header = "".join(f"{k}: {v}\r\n" for k, v in headers.items())
            ffmpeg_params.extend(["-headers", built_header])
            have_header = True

        try:
            proc = await asyncio.create_subprocess_exec(
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "stream=width,height,codec_type,codec_name",
                "-of",
                "json",
                path,
                *ffmpeg_params,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except FileNotFoundError:
            raise FFmpegNotInstalled("ffprobe/ffmpeg tidak ditemukan di PATH")

        try:
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=15)
            result = json.loads(stdout.decode("utf-8")) or {}
            streams = result.get("streams", [])
        except (asyncio.TimeoutError, JSONDecodeError):
            proc.kill()
            return None

        have_video = False
        have_audio = False
        have_valid_video = False
        width = height = 0

        image_codecs = {"png", "jpeg", "jpg", "mjpeg"}

        for stream in streams:
            codec_type = stream.get("codec_type", "")
            codec_name = stream.get("codec_name", "")

            if codec_type == "video" and not (
                not needed_image and codec_name in image_codecs
            ):
                have_video = True
                width = int(stream.get("width", 0) or 0)
                height = int(stream.get("height", 0) or 0)
                if width and height:
                    have_valid_video = True

            elif codec_type == "audio":
                have_audio = True

        if needed_video:
            if not have_video:
                raise NoVideoSourceFound(path)
            if not have_valid_video:
                raise InvalidVideoProportion("Video proportion not found")

        if needed_audio and not have_audio:
            raise NoAudioSourceFound(path)

        if needed_audio and not needed_video:
            return have_header
        if have_video:
            return width, height, have_header
        return None
