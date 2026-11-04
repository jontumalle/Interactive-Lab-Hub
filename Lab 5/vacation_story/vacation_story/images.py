"""Extract source metadata before preparing orientation-corrected, private JPEGs."""
from datetime import datetime
import math
import os
from pathlib import Path
from uuid import uuid4

from PIL import Image, ImageOps, UnidentifiedImageError
from pillow_heif import register_heif_opener

register_heif_opener()
# JPEG files with auxiliary images (such as an HDR gain map) can be identified
# by Pillow as MPO. Their primary frame is still a supported JPEG photograph.
ACCEPTED = {'JPEG', 'MPO', 'PNG', 'WEBP', 'HEIF', 'HEIC'}


def text(value):
    if isinstance(value, bytes):
        value = value.decode('utf-8', errors='replace')
    return value.strip('\x00 \n') if isinstance(value, str) and value.strip('\x00 \n') else None


def metadata_from(image):
    exif = image.getexif()
    try:
        details = exif.get_ifd(34665)
    except (KeyError, TypeError, ValueError):
        details = {}
    values = dict(exif) | details
    captured = None
    # DateTime is an editing date, so only original/digitized capture tags qualify.
    for tag, offset_tag in ((36867, 36881), (36868, 36882)):
        raw = text(values.get(tag))
        if raw:
            try:
                captured = datetime.strptime(raw, '%Y:%m:%d %H:%M:%S').isoformat()
                offset = text(values.get(offset_tag))
                if offset:
                    captured = datetime.fromisoformat(captured + offset).isoformat()
                break
            except ValueError:
                captured = None
    latitude = longitude = None
    try:
        gps = exif.get_ifd(34853)
        def coordinate(parts, ref):
            result = float(parts[0]) + float(parts[1]) / 60 + float(parts[2]) / 3600
            return -result if ref in ('S', 'W', b'S', b'W') else result
        latitude = coordinate(gps[2], gps[1])
        longitude = coordinate(gps[4], gps[3])
        if not (math.isfinite(latitude) and math.isfinite(longitude) and -90 <= latitude <= 90 and -180 <= longitude <= 180):
            latitude = longitude = None
    except (KeyError, TypeError, ValueError, ZeroDivisionError, IndexError):
        pass
    description = text(values.get(270)) or text(image.info.get('Description')) or text(image.info.get('description'))
    return dict(captured_at=captured, latitude=latitude, longitude=longitude,
                place_name=None, embedded_description=description)


def ingest(stream, directory: Path, settings: dict, order: int) -> dict:
    photo_id = uuid4().hex
    paths = [directory / 'photos' / f'{photo_id}.jpg', directory / 'analysis' / f'{photo_id}.jpg']
    try:
        with Image.open(stream) as original:
            if original.format not in ACCEPTED:
                raise ValueError(f'This file contains {original.format or "an unknown image format"}. Choose a JPEG, PNG, WebP, or HEIC/HEIF photo.')
            if original.format == 'MPO':
                # Do not treat the auxiliary HDR/depth image as another trip photo.
                original.seek(0)
            metadata = metadata_from(original)
            prepared = ImageOps.exif_transpose(original)
            # Composite transparency on white rather than create black silhouettes.
            if prepared.mode in ('RGBA', 'LA') or 'transparency' in prepared.info:
                rgba = prepared.convert('RGBA')
                background = Image.new('RGBA', rgba.size, 'white')
                prepared = Image.alpha_composite(background, rgba).convert('RGB')
            else:
                prepared = prepared.convert('RGB')
            for path, edge in zip(paths, (settings['prepared_max_edge'], settings['analysis_max_edge'])):
                path.parent.mkdir(exist_ok=True)
                copy = prepared.copy()
                copy.thumbnail((edge, edge), Image.Resampling.LANCZOS)
                # No EXIF in output: extracted metadata stays in private JSON.
                with path.open('wb') as target:
                    copy.save(target, format='JPEG', quality=settings['jpeg_quality'])
                    target.flush()
                    os.fsync(target.fileno())
        return dict(id=photo_id, prepared_image_path=str(paths[0].resolve()),
                    analysis_image_path=str(paths[1].resolve()), submission_order=order,
                    metadata=metadata.copy(), extracted_metadata=metadata.copy(),
                    user_description=metadata['embedded_description'] or '', vibes=[])
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as error:
        for path in paths:
            path.unlink(missing_ok=True)
        raise ValueError('This photo could not be read. Try another supported image.') from error
    except Exception:
        for path in paths:
            path.unlink(missing_ok=True)
        raise
