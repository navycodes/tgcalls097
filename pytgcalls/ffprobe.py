import asyncio
import json
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
    IMAGE_CODECS = {"png", "jpeg", "jpg", "mjpeg"}

    @staticmethod
    def build_headers(headers: Optional[Dict[str, str]]) -> List[str]:
        if not headers:
            return []
        built = "".join(f"{k}: {v}\r\n" for k, v in headers.items())
        return ["-headers", built]

    @staticmethod
    async def check_file(
        path: str,
        needed_audio: bool = False,
        needed_video: bool = False,
        needed_image: bool = False,
        headers: Optional[Dict[str, str]] = None,
        timeout: int = 10,
    ) -> Union[Tuple[int, int, bool], bool, None]:
        ffmpeg_params: List[str] = []
        have_header = False

        if headers and check_support(path):
            ffmpeg_params.extend(FFprobe.build_headers(headers))
            have_header = True

        try:
            proc = await asyncio.create_subprocess_exec(
                "ffprobe",
                "-v", "error",
                "-show_entries", "stream=width,height,codec_type,codec_name",
                "-of", "json",
                path,
                *ffmpeg_params,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )
        except FileNotFoundError:
            raise FFmpegNotInstalled("ffprobe/ffmpeg tidak ditemukan di PATH")

        try:
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            if not stdout:
                return None
            result = json.loads(stdout.decode("utf-8"))
        except (asyncio.TimeoutError, JSONDecodeError):
            proc.kill()
            return None

        streams = result.get("streams", [])
        if not streams:
            return None

        have_video = have_audio = have_valid_video = False
        width = height = 0

        for stream in streams:
            codec_type = stream.get("codec_type")
            codec_name = stream.get("codec_name", "")

            if codec_type == "video":
                if not (not needed_image and codec_name in FFprobe.IMAGE_CODECS):
                    have_video = True
                    width = int(stream.get("width") or 0)
                    height = int(stream.get("height") or 0)
                    if width and height:
                        have_valid_video = True
                    if have_audio or not needed_audio:
                        break

            elif codec_type == "audio":
                have_audio = True
                if have_video or not needed_video:
                    break

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
