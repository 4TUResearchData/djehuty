"""
Shared imaging helpers.

Extracted from ``djehuty.web.wsgi.__generate_thumbnail`` so both the legacy
Werkzeug server and the FastAPI handlers can produce identical thumbnails
without depending on the legacy ``ApiServer`` instance.
"""

from __future__ import annotations

import logging
import os

from PIL import Image, ImageSequence, UnidentifiedImageError

from djehuty.web import s3
from djehuty.web.config import config

_log = logging.getLogger(__name__)


def image_mimetype(file_path) -> str | None:
    """Return the MIME type of ``file_path`` if PIL can identify it as an image.

    Returns ``None`` for missing files or formats PIL does not recognise.
    """
    try:
        with Image.open(file_path) as image:
            return image.get_format_mimetype()
    except (FileNotFoundError, UnidentifiedImageError, OSError):
        return None


def generate_thumbnail(
    input_filename,
    dataset_uuid: str,
    max_width: int = 300,
    max_height: int = 300,
) -> str | None:
    """Render a thumbnail for ``input_filename`` and persist it.

    Args:
        input_filename: A filesystem path or an ``s3.S3DownloadStreamer``.
        dataset_uuid:   UUID used to name the output file
                        (``<thumbnail_storage>/<uuid>.<ext>``).
        max_width:      Maximum thumbnail width in pixels.
        max_height:     Maximum thumbnail height in pixels.

    Returns:
        The lowercase image extension on success, or ``None`` if generation
        fails (unsupported format, missing file, etc.).
    """
    try:
        s3_cached_file = None
        original = None
        if isinstance(input_filename, s3.S3DownloadStreamer):
            s3_cached_file = s3.s3_temporary_file(input_filename)
            original = Image.open(s3_cached_file)
        else:
            original = Image.open(input_filename)

        extension = original.format.lower()
        output_filename = os.path.join(config.thumbnail_storage, f"{dataset_uuid}.{extension}")

        # When the image already matches the thumbnail size, save unchanged.
        if original.width == max_width and original.height == max_height:
            original.save(output_filename)
            return None

        # Determine scaled-down dimensions preserving aspect ratio.
        if original.width > original.height:
            thumb_height = int(original.height * (max_width / original.width))
            thumb_width = max_width
        else:
            thumb_height = max_height
            thumb_width = int(original.width * (max_height / original.height))

        # Preserve animation in GIFs.
        if extension == "gif":
            frames = []
            try:
                original_durations = [
                    frame.info["duration"] for frame in ImageSequence.Iterator(original)
                ]
            except KeyError:
                original_durations = 50
            for frame in ImageSequence.Iterator(original):
                resized_frame = frame.resize((thumb_width, thumb_height), Image.Resampling.LANCZOS)
                frames.append(resized_frame)

            first_frame_size = frames[0].size
            resized_image = Image.new(
                "RGBA",
                (first_frame_size[0] * len(frames), first_frame_size[1]),
            )

            for index, frame in enumerate(frames):
                resized_image.paste(frame, (index * first_frame_size[0], 0))
                frames[index] = resized_image.crop(
                    (
                        index * first_frame_size[0],
                        0,
                        (index + 1) * first_frame_size[0],
                        first_frame_size[1],
                    )
                )
            frames[0].save(
                output_filename,
                save_all=True,
                append_images=frames[1:],
                loop=0,
                duration=original_durations,
            )
            return extension

        thumbnail = original.resize((thumb_width, thumb_height))
        thumbnail.save(output_filename)

        if s3_cached_file is not None:
            os.remove(s3_cached_file)

        return extension
    except (FileNotFoundError, UnidentifiedImageError) as error:
        _log.error("Failed to create thumbnail: %s", error)

    return None
