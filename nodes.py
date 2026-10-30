"""NG8 metadata nodes: lossless PNG and metadata-only ExifTool updates."""
import os
import re
import shutil
import subprocess
import tempfile
import urllib.request
import urllib.parse
import html
import zipfile
import threading
import logging
from pathlib import Path
import numpy as np
from PIL import Image, PngImagePlugin
import folder_paths

ROOT = Path(__file__).resolve().parent
TAG = '@Network_Guy8'

_download_lock = threading.Lock()

def exiftool():
    """Install a pinned, SHA256-verified Windows ExifTool release on first use.

    GitHub's release assets avoid SourceForge's HTML anti-bot/redirect responses.
    This pinned mirror is a fallback for ExifTool's official SourceForge distribution.
    """
    local = ROOT / 'tools' / 'exiftool.exe'
    def working():
        if not local.is_file():
            return False
        try:
            result = subprocess.run([str(local), '-ver'], capture_output=True, text=True, timeout=30)
            return result.returncode == 0 and bool(result.stdout.strip())
        except (OSError, subprocess.TimeoutExpired):
            return False
    if working():
        return str(local)
    with _download_lock:
        if working():
            return str(local)
        if os.name != 'nt':
            installed = shutil.which('exiftool')
            if installed:
                return installed
            raise RuntimeError('Automatic portable ExifTool installation currently supports Windows only')
        # Published release asset and SHA256 from TwelveOrg/ExifTool v13.29.
        # Pinning the checksum avoids trusting mutable release-page content.
        url = 'https://github.com/TwelveOrg/ExifTool/releases/download/v13.29/exiftool-13.29-win64.zip'
        expected_sha256 = 'ae8e1fc95266aa5f2769e16cd940f88bf80fa408484ab10a8808895992e1cfb6'
        logging.info('[NG8 Metadata] Downloading SHA256-verified portable ExifTool 13.29 from GitHub')
        try:
            with tempfile.TemporaryDirectory(prefix='ng8_exiftool_') as td:
                td = Path(td)
                archive = td / 'exiftool.zip'
                req = urllib.request.Request(url, headers={'User-Agent': 'NG8-ComfyUI-Metadata/13', 'Accept': 'application/octet-stream'})
                with urllib.request.urlopen(req, timeout=120) as response, archive.open('wb') as target:
                    shutil.copyfileobj(response, target)
                digest = __import__('hashlib').sha256(archive.read_bytes()).hexdigest()
                if digest.lower() != expected_sha256:
                    raise RuntimeError('Downloaded file SHA256 does not match the published release checksum; refusing to execute it')
                if not zipfile.is_zipfile(archive):
                    raise RuntimeError('Downloaded release asset is not a ZIP archive')
                staging = td / 'staging'
                staging.mkdir()
                with zipfile.ZipFile(archive) as zf:
                    names = zf.namelist()
                    exe_entry = next((n for n in names if n.replace('\\','/').split('/')[-1].lower() in ('exiftool.exe','exiftool(-k).exe')), None)
                    if not exe_entry:
                        raise RuntimeError('Archive does not contain exiftool.exe')
                    exe_parent = exe_entry.replace('\\','/').rsplit('/',1)[0]
                    for name in names:
                        normalized = name.replace('\\','/')
                        if normalized.endswith('/'):
                            continue
                        segments = normalized.split('/')
                        if 'exiftool_files' not in segments:
                            continue
                        i = segments.index('exiftool_files')
                        rel = Path(*segments[i:])
                        if '..' in rel.parts:
                            raise RuntimeError('Unsafe archive path')
                        dest = staging / rel
                        dest.parent.mkdir(parents=True,exist_ok=True)
                        with zf.open(name) as inp, dest.open('wb') as out:
                            shutil.copyfileobj(inp,out)
                    with zf.open(exe_entry) as inp, (staging / 'exiftool.exe').open('wb') as out:
                        shutil.copyfileobj(inp,out)
                if not (staging / 'exiftool_files').is_dir():
                    raise RuntimeError('Archive is missing the required exiftool_files directory')
                check = subprocess.run([str(staging / 'exiftool.exe'), '-ver'], capture_output=True, text=True, timeout=40)
                if check.returncode != 0:
                    raise RuntimeError('Extracted ExifTool failed version check: ' + check.stderr)
                tools = ROOT / 'tools'
                tools.mkdir(parents=True, exist_ok=True)
                shutil.copytree(staging / 'exiftool_files', tools / 'exiftool_files', dirs_exist_ok=True)
                shutil.copy2(staging / 'exiftool.exe', local)
                logging.info('[NG8 Metadata] ExifTool %s installed successfully', check.stdout.strip())
                return str(local)
        except Exception as exc:
            raise RuntimeError('NG8 automatic ExifTool installation failed from verified GitHub release: ' + str(exc)) from exc

def stamp(path, creator, copyright_text, description):
    # ExifTool modifies metadata without decoding/re-encoding media.
    cmd = [exiftool(), '-overwrite_original', '-m',
           '-Artist=' + creator, '-Creator=' + creator,
           '-Copyright=' + copyright_text,
           '-Description=' + description,
           '-XMP-dc:Creator=' + creator,
           '-XMP-dc:Rights=' + copyright_text,
           '-XMP-dc:Description=' + description,
           '-QuickTime:Artist=' + creator,
           '-QuickTime:Copyright=' + copyright_text,
           '-QuickTime:Description=' + description,
           str(path)]
    # Some tags are format-specific; unsupported tags can cause warnings.
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    if result.returncode != 0:
        raise RuntimeError(f'ExifTool failed for {path}: {result.stderr or result.stdout}')

class NG8SaveImage:
    @classmethod
    def INPUT_TYPES(cls):
        return {'required': {'images': ('IMAGE',), 'filename_prefix': ('STRING', {'default': 'NG8'}),
                             'creator': ('STRING', {'default': TAG}),
                             'copyright': ('STRING', {'default': '© 2026 @Network_Guy8'}),
                             'description': ('STRING', {'default': 'AI-generated artwork'}),
                             'format': (['PNG', 'JPEG', 'WebP', 'TIFF'], {'default': 'PNG'}),
                             'color': (['RGB', 'RGBA', 'Grayscale'], {'default': 'RGB'}),
                             'bit_depth': (['8', '16'], {'default': '8'}),
                             'color_space': (['sRGB', 'Linear sRGB'], {'default': 'sRGB'}),
                             'srgb': ('BOOLEAN', {'default': True})}}
    RETURN_TYPES = ('IMAGE', 'STRING')
    RETURN_NAMES = ('image', 'saved_paths')
    FUNCTION = 'save'
    OUTPUT_NODE = True
    CATEGORY = 'NG8/Metadata'
    def save(self, images, filename_prefix, creator, copyright, description, format, color, bit_depth, color_space, srgb):
        outdir = Path(folder_paths.get_output_directory())
        prefix = re.sub(r'[^\w. -]', '_', filename_prefix).strip(' .') or 'NG8'
        fmt = format.upper()
        depth = int(bit_depth)
        if depth == 16 and fmt in ('JPEG', 'WebP'):
            raise ValueError(f'{fmt} export only supports 8-bit per channel in this node. Choose PNG or TIFF for 16-bit.')
        if color == 'RGBA' and fmt == 'JPEG':
            raise ValueError('JPEG does not support alpha. Choose RGB/Grayscale or another format.')
        if color_space == 'Linear sRGB' and fmt in ('JPEG', 'WebP'):
            raise ValueError('Linear sRGB output is not supported for JPEG/WebP. Choose sRGB or PNG/TIFF.')
        paths = []
        for i, tensor in enumerate(images):
            values = np.clip(tensor.cpu().numpy(), 0.0, 1.0)
            if values.ndim != 3 or values.shape[-1] not in (1, 3, 4):
                raise ValueError('Expected H×W×1/3/4 image tensor')
            # ComfyUI IMAGE tensors conventionally contain sRGB-encoded values.
            if color_space == 'Linear sRGB' and srgb:
                rgb = values[..., :3]
                values = values.copy()
                values[..., :3] = np.where(rgb <= 0.04045, rgb / 12.92, ((rgb + 0.055) / 1.055) ** 2.4)
            if values.shape[-1] == 1:
                rgb = np.repeat(values, 3, axis=-1)
                alpha = np.ones((*values.shape[:2], 1), dtype=values.dtype)
            else:
                rgb = values[..., :3]
                alpha = values[..., 3:4] if values.shape[-1] == 4 else np.ones((*values.shape[:2], 1), dtype=values.dtype)
            if color == 'Grayscale':
                values = (rgb[..., 0] * 0.2126 + rgb[..., 1] * 0.7152 + rgb[..., 2] * 0.0722)
            elif color == 'RGBA':
                values = np.concatenate((rgb, alpha), axis=-1)
            else:
                values = rgb
            depth = int(bit_depth)
            arr = np.rint(np.clip(values, 0, 1) * (65535 if depth == 16 else 255)).astype(np.uint16 if depth == 16 else np.uint8)
            meta = PngImagePlugin.PngInfo()
            meta.add_text('Creator', creator)
            meta.add_text('Copyright', copyright)
            meta.add_text('Description', description)
            meta.add_text('ColorSpace', color_space)
            if srgb and color_space == 'sRGB':
                meta.add_text('sRGB', 'true')
            ext = {'PNG': '.png', 'JPEG': '.jpg', 'WebP': '.webp', 'TIFF': '.tiff'}[fmt]
            fd, tmp = tempfile.mkstemp(prefix='ng8_', suffix=ext, dir=outdir)
            os.close(fd)
            try:
                if depth == 16 and color != 'Grayscale':
                    # OpenCV writes 16-bit PNG/TIFF RGB(A) without reducing depth.
                    try:
                        import cv2
                    except ImportError as exc:
                        raise RuntimeError('16-bit RGB/RGBA export requires opencv-python (cv2)') from exc
                    encoded = arr[..., [2, 1, 0, 3]] if color == 'RGBA' else arr[..., ::-1]
                    if not cv2.imwrite(tmp, encoded):
                        raise RuntimeError(f'OpenCV failed to write 16-bit {fmt}')
                else:
                    im = Image.fromarray(arr)
                    if fmt == 'PNG':
                        im.save(tmp, format='PNG', pnginfo=meta)
                    elif fmt == 'JPEG':
                        im.save(tmp, format='JPEG', quality=95, subsampling=0)
                    elif fmt == 'WebP':
                        im.save(tmp, format='WEBP', lossless=True)
                    elif fmt == 'TIFF':
                        im.save(tmp, format='TIFF', compression='tiff_lzw')
                stamp(tmp, creator, copyright, description)
                base = outdir / f'{prefix}_{i:05d}{ext}'
                target = base
                n = 1
                while target.exists():
                    target = outdir / f'{prefix}_{i:05d}_{n}{ext}'
                    n += 1
                os.replace(tmp, target)
                paths.append(str(target))
            finally:
                if os.path.exists(tmp): os.unlink(tmp)
        return {
            'ui': {
                'images': [
                    {'filename': Path(path).name, 'subfolder': '', 'type': 'output'}
                    for path in paths
                ]
            },
            'result': (images, '\n'.join(paths))
        }

class NG8TagVideo:
    @classmethod
    def INPUT_TYPES(cls):
        return {'required': {'video_path': ('STRING', {'default': '', 'multiline': False}),
                             'creator': ('STRING', {'default': TAG}),
                             'copyright': ('STRING', {'default': '© 2026 @Network_Guy8'}),
                             'description': ('STRING', {'default': 'AI-generated video'}),
                             'suffix': ('STRING', {'default': '_NG8'})}}
    RETURN_TYPES = ('STRING',)
    RETURN_NAMES = ('output_path',)
    FUNCTION = 'tag'
    OUTPUT_NODE = True
    CATEGORY = 'NG8/Metadata'
    def tag(self, video_path, creator, copyright, description, suffix):
        p = Path(video_path.strip().strip('"')).expanduser()
        if not p.is_absolute(): p = Path(folder_paths.get_output_directory()) / p
        p = p.resolve()
        if not p.is_file(): raise FileNotFoundError(f'Video does not exist: {p}')
        if p.suffix.lower() not in {'.mp4', '.mov', '.m4v', '.3gp'}:
            raise ValueError('Supported video formats: MP4, MOV, M4V, 3GP')
        clean_suffix = re.sub(r'[^\w-]', '_', suffix) or '_NG8'
        target = p.with_name(p.stem + clean_suffix + p.suffix)
        n = 1
        while target.exists():
            target = p.with_name(f'{p.stem}{clean_suffix}_{n}{p.suffix}')
            n += 1
        shutil.copy2(p, target)
        try:
            stamp(target, creator, copyright, description)
        except Exception:
            target.unlink(missing_ok=True)
            raise
        return (str(target),)

NODE_CLASS_MAPPINGS = {'NG8SaveImage': NG8SaveImage, 'NG8TagVideo': NG8TagVideo}
NODE_DISPLAY_NAME_MAPPINGS = {'NG8SaveImage': 'NG8 Save Image + Creator Metadata', 'NG8TagVideo': 'NG8 Tag Existing Video (No Re-encode)'}


class NG8SaveVideo:
    """Save a native ComfyUI VIDEO and apply metadata after the initial encode."""
    @classmethod
    def INPUT_TYPES(cls):
        return {'required': {
            'video': ('VIDEO',),
            'filename_prefix': ('STRING', {'default': 'video/NG8'}),
            'format': (['auto', 'mp4', 'mkv', 'webm'], {'default': 'auto'}),
            'codec': (['auto', 'h264', 'av1'], {'default': 'auto'}),
            'creator': ('STRING', {'default': TAG}),
            'copyright': ('STRING', {'default': '© 2026 @Network_Guy8'}),
            'description': ('STRING', {'default': 'AI-generated video'}),
        }}
    RETURN_TYPES = ('VIDEO', 'STRING')
    RETURN_NAMES = ('video', 'saved_path')
    FUNCTION = 'save'
    OUTPUT_NODE = True
    CATEGORY = 'NG8/Metadata'

    def save(self, video, filename_prefix, format, codec, creator, copyright, description):
        # Native ComfyUI VIDEO API: Create Video -> VIDEO -> save_to.
        # Saving raw frames encodes once; metadata stamping never re-encodes.
        from comfy_api.latest import Types
        width, height = video.get_dimensions()
        output_dir, name, counter, subfolder, _ = folder_paths.get_save_image_path(
            filename_prefix, folder_paths.get_output_directory(), width, height)
        # Match native Save Video's format and codec choices. ExifTool can
        # reliably write creator metadata to MP4, not MKV/WebM.
        chosen_format = 'mp4' if format == 'auto' else format
        if chosen_format != 'mp4':
            raise ValueError('NG8 creator metadata currently supports MP4 only. Select mp4 or auto; MKV/WebM cannot be tagged reliably with ExifTool.')
        filename = f'{name}_{counter:05d}.{chosen_format}'
        path = Path(output_dir) / filename
        # Check tool availability before spending time encoding.
        exiftool()
        if path.exists():
            raise FileExistsError(f'Refusing to overwrite existing video: {path}')
        try:
            video.save_to(str(path), format=Types.VideoContainer(chosen_format),
                          codec=Types.VideoCodec(codec), metadata=None)
            stamp(path, creator, copyright, description)
        except Exception:
            path.unlink(missing_ok=True)
            raise
        # Match the standard ComfyUI video preview payload. Keep the VIDEO
        # passthrough so existing downstream connections remain usable.
        preview = {'filename': filename, 'subfolder': subfolder, 'type': 'output', 'format': f'video/{chosen_format}'}
        return {'ui': {'videos': [preview], 'gifs': [preview]}, 'result': (video, str(path))}

NODE_CLASS_MAPPINGS['NG8SaveVideo'] = NG8SaveVideo
NODE_DISPLAY_NAME_MAPPINGS['NG8SaveVideo'] = 'NG8 Save Video + Creator Metadata (VIDEO)'


class NG8TagVHSVideo:
    """Tag the completed file from VideoHelperSuite Video Combine's VHS_FILENAMES output."""
    @classmethod
    def INPUT_TYPES(cls):
        return {'required': {
            'filenames': ('VHS_FILENAMES',),
            'creator': ('STRING', {'default': TAG}),
            'copyright': ('STRING', {'default': '© 2026 @Network_Guy8'}),
            'description': ('STRING', {'default': 'AI-generated video'}),
        }}
    RETURN_TYPES = ('STRING',)
    RETURN_NAMES = ('saved_paths',)
    FUNCTION = 'tag'
    OUTPUT_NODE = True
    CATEGORY = 'NG8/Metadata'

    def tag(self, filenames, creator, copyright, description):
        # VHS_FILENAMES is typically (save_output_bool, [filepaths]) in VHS,
        # but accommodate other tuple/list/dict shapes without assuming a path
        # is a plain STRING. Never scan arbitrary directories for 'latest' files.
        def flatten(obj):
            if isinstance(obj, (str, os.PathLike)):
                yield os.fspath(obj)
            elif isinstance(obj, dict):
                for key in ('filenames', 'files', 'paths', 'output', 'gifs'):
                    if key in obj:
                        yield from flatten(obj[key])
            elif isinstance(obj, (tuple, list)):
                for item in obj:
                    yield from flatten(item)

        candidates = list(dict.fromkeys(flatten(filenames)))
        if not candidates:
            raise ValueError('VideoHelperSuite returned no filenames. Set Video Combine save_output=true.')
        output_dir = Path(folder_paths.get_output_directory()).resolve()
        temp_dir = Path(folder_paths.get_temp_directory()).resolve()
        source_paths = []
        for raw in candidates:
            path = Path(raw).expanduser()
            if not path.is_absolute():
                # VHS normally returns absolute paths. Support output-relative
                # paths without accidentally using the ComfyUI process cwd.
                path = output_dir / path
            path = path.resolve()
            if path.suffix.lower() not in ('.mp4', '.mov', '.m4v', '.3gp'):
                continue
            # VideoHelperSuite can report the base MP4 even when muxing audio
            # actually saved <stem>-audio.mp4. Prefer the audio-bearing final
            # file when present, and never guess unrelated files or directories.
            audio_path = path.with_name(path.stem + '-audio' + path.suffix)
            if not path.stem.endswith('-audio') and audio_path.is_file():
                path = audio_path.resolve()
            if not path.is_file():
                raise FileNotFoundError(
                    f'VideoHelperSuite video does not exist: {path} '
                    f'(also checked {audio_path})')
            if not (path.is_relative_to(output_dir) or path.is_relative_to(temp_dir)):
                raise ValueError(f'Refusing to modify file outside ComfyUI output/temp: {path}')
            source_paths.append(path)
        if not source_paths:
            raise ValueError('No supported MP4/MOV video found in VideoHelperSuite Filenames. Select video/h264-mp4 and save_output=true.')
        # Stage metadata changes in a temporary file beside the original, then
        # atomically replace it. A failed metadata write leaves the original intact.
        tool = exiftool()
        results = []
        for source in dict.fromkeys(source_paths):
            fd, staged_name = tempfile.mkstemp(prefix='.ng8_tag_', suffix=source.suffix, dir=str(source.parent))
            os.close(fd)
            staged = Path(staged_name)
            try:
                shutil.copy2(source, staged)
                stamp(staged, creator, copyright, description)
                check = subprocess.run([tool, '-s3', '-XMP-dc:Creator', '-QuickTime:Artist', str(staged)],
                                       capture_output=True, text=True, timeout=60)
                if check.returncode != 0 or creator not in check.stdout:
                    raise RuntimeError(f'NG8 could not verify creator metadata on {source}: {check.stderr or check.stdout}')
                os.replace(staged, source)
                results.append(str(source))
            finally:
                staged.unlink(missing_ok=True)
        return ('\n'.join(results),)

NODE_CLASS_MAPPINGS['NG8TagVHSVideo'] = NG8TagVHSVideo
NODE_DISPLAY_NAME_MAPPINGS['NG8TagVHSVideo'] = 'NG8 Tag VHS Video In Place (No Re-encode)'

