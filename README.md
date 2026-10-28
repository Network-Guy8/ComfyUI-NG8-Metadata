# NG8 Metadata — v0.16 Beta

**Creator:** [@Network_Guy8](https://x.com/Network_Guy8)  
**Platform:** ComfyUI on Windows (tested by the creator)  
**Status:** Community beta — working in the creator's setup; other configurations need testing.

Add creator, copyright, and description metadata when saving ComfyUI images or MP4 videos, or tag the final MP4 from VideoHelperSuite without re-encoding. Default creator is `@Network_Guy8`; all creator/copyright/description fields are editable.

## Installation

1. Download this release ZIP and extract it.
2. Copy the enclosed **`ComfyUI-NG8-Metadata`** folder into your ComfyUI **`custom_nodes`** directory. Example: `D:\ComfyUI_minimax\ComfyUI\custom_nodes\ComfyUI-NG8-Metadata\`.
3. If upgrading, replace the old package files but **preserve the existing `tools` folder** if ExifTool was previously downloaded.
4. Restart ComfyUI, then **hard-refresh the browser (Ctrl+Shift+R)** so the new preview JavaScript loads. Find the nodes under **NG8/Metadata**.

The package uses Python libraries already common in ComfyUI (`numpy`, `Pillow`, and `folder_paths`). **16-bit RGB/RGBA image export also requires `cv2`**. No extra Python installation should be needed for typical ComfyUI setups.

### Automatic ExifTool setup

On first metadata operation on Windows, NG8 automatically downloads a **pinned third-party Windows ExifTool build** (13.29) from the [TwelveOrg/ExifTool GitHub release](https://github.com/TwelveOrg/ExifTool/releases/tag/v13.29), verifies its SHA-256, checks that it runs, and caches it in this package's `tools` folder. This is **not ExifTool's official distribution host**. An internet connection to GitHub release assets is required the first time. The executable is not included in this ZIP. The node reuses the installed executable on subsequent runs. No administrator rights or system-wide ExifTool installation is intended.

The auto-installer is Windows-only. On other platforms, the node can use an existing `exiftool` on `PATH`, but automatic installation is not implemented.

## Nodes and wiring

### 1. NG8 Save Image + Creator Metadata

Connect the image output (for example, **VAE Decode → IMAGE**) to **NG8 Save Image + Creator Metadata → images**. Choose PNG, JPEG, WebP, or TIFF; color mode, bit depth, and color-space controls are available. The node saves tagged images in the ComfyUI output folder and returns the original IMAGE and saved paths. **16-bit JPEG/WebP is not supported**; 16-bit RGB/RGBA PNG/TIFF needs OpenCV.

### 2. NG8 Save Video + Creator Metadata (VIDEO)

Connect **Create Video → VIDEO** to **NG8 Save Video + Creator Metadata (VIDEO) → video**. Set format to **auto** or **mp4**. The node encodes the native VIDEO once, tags the resulting MP4, and uses a frontend extension to display an HTML5 video preview inside the node. Output names use the form `NG8_00001.mp4` (no trailing underscore). Creator/copyright/description can be customized.

**Important:** This node currently supports MP4 metadata tagging only. MKV/WebM options are rejected rather than silently writing an untagged file. The codec selection depends on the installed ComfyUI video backend.

### 3. NG8 Tag VHS Video In Place (No Re-encode)

For **VideoHelperSuite Video Combine**, keep **`save_output = true`** and connect:

`Video Combine: Filenames (VHS_FILENAMES) → NG8 Tag VHS Video In Place: filenames`

That's the **only wire** needed for metadata. Leave Video Combine's frame rate, audio, format, codec, and quality settings as you normally use them. When VHS reports `name.mp4` but actually saves `name-audio.mp4`, NG8 locates and tags the audio-bearing MP4. When both files exist, it prefers the `-audio` version.

**No re-encode:** NG8 copies the completed MP4 to a temporary file in the same folder, writes and verifies the metadata, then atomically replaces the original. It does not intentionally leave a second tagged MP4. **You need temporary free disk space roughly equal to the video size.** If tagging fails before replacement, the original remains untouched.

### 4. NG8 Tag Existing Video (No Re-encode)

An optional utility for a manually specified existing video path. **Unlike the VHS in-place node, this one makes a new tagged copy** using the configured suffix (default `_NG8`). Supported extensions: MP4, MOV, M4V, and 3GP.

## How to verify metadata

With ExifTool installed, run:

```powershell
& "D:\ComfyUI_minimax\ComfyUI\custom_nodes\ComfyUI-NG8-Metadata\tools\exiftool.exe" -G1 -a -s "D:\path\to\your\video.mp4"
```

Look for creator, artist, copyright, and description fields. The exact writable tags depend on file format and ExifTool support. Embedded metadata **does not guarantee** that social networks preserve it after upload.

## Troubleshooting

- **Download error:** Confirm GitHub release assets are reachable and antivirus/security tools permit the portable executable. Share the full NG8 error log when reporting an issue.
- **VHS file not found:** Check that Video Combine has `save_output=true`, and report both the filename from VHS and the actual filename on disk.
- **Video preview not shown:** Try refreshing the ComfyUI page; include your ComfyUI version and frontend version in the report.
- **Only one final MP4 wanted:** Use the **VHS in-place** node, not the **Tag Existing Video** copy node.
- **Update:** Stop ComfyUI, replace package files, keep `tools`, restart, and refresh.

## Community feedback

Please report your **Windows version**, **ComfyUI version**, **native VIDEO vs VideoHelperSuite workflow**, **output format**, and any **console traceback**. A short description of whether the MP4 still plays with audio and whether its metadata is visible is especially helpful.

## Distribution notes

This ZIP contains the NG8 Python nodes and documentation, **not ExifTool itself**. ExifTool is a separate third-party project by Phil Harvey. The auto-downloaded executable is hosted by a third party; see the linked release for provenance. No open-source license for this NG8 package is declared in this beta; obtain permission from the creator before redistributing modified code.

## Native video preview troubleshooting

The `web/ng8_video_preview.js` frontend extension adds the actual video player to the NG8 native Save Video node; returning `ui.videos` from Python alone does not guarantee a preview. After upgrading, restart ComfyUI and hard-refresh the browser. The preview appears after a successful execution of the node. If the MP4 plays from the output folder but the preview is blank, inspect the browser console for `NG8.Metadata.VideoPreview` errors and check whether the `/view` endpoint loads the MP4. The preview feature has not yet been validated across all ComfyUI frontend versions.
