## NG8 Metadata v0.17 Beta — Responsive Video Preview

The first public beta release of **ComfyUI-NG8-Metadata**, a collection of custom nodes for saving images and videos with embedded creator metadata.

Designed for AI content creators who want to preserve attribution information in their generated media.

### Features

- **Image Metadata Saving** — Save generated images with embedded creator and copyright metadata.
- **Native Video Saving** — Save videos directly from ComfyUI with embedded metadata.
- **Responsive Video Preview** — Video previews automatically resize with the node while preserving the original aspect ratio.
- **VideoHelperSuite (VHS) Support** — Add metadata to existing VHS-generated video files without re-encoding.
- **Automatic ExifTool Installation** — Downloads and caches ExifTool when needed.
- **No Video Re-encoding for Metadata Updates** — Preserve the original video quality.
- **Creator Attribution** — Support for creator names, copyright information, and other metadata fields.

### What's New in v0.17

- Removed the fixed 420px video preview height restriction.
- Improved preview resizing when adjusting node dimensions.
- Reduced the minimum preview height from 220px to 120px.
- Preserved existing video playback controls and metadata functionality.

### Installation

1. Download the release ZIP.
2. Extract the `ComfyUI-NG8-Metadata` folder into `ComfyUI/custom_nodes/`.
3. Restart ComfyUI.
4. Hard-refresh your browser (`Ctrl+Shift+R`) to load the updated preview JavaScript.

### Beta Testing

This is a public beta release. Feedback, bug reports, and feature suggestions are welcome through GitHub Issues.

**Created by @Network_Guy8 (NG8)**

*Version 0.17 Beta — October 2026*

### NG8 Save Image Thumbnail Preview

NG8 Save Image + Creator Metadata now displays a thumbnail of the saved image directly inside the ComfyUI node after execution.

- Supports the existing PNG, JPEG, WebP, and TIFF saving options.
- Preserves creator, copyright, and description metadata.
- Continues returning the original IMAGE and saved file paths.
- Uses ComfyUI's native image preview system.
