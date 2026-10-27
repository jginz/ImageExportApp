# Confocal Deck Builder

Drag a folder of confocal exports (`*.tif.frames`) onto the window. It makes one slide per image:
merged image on the left, four channel panels on the right. Channel names are read from the filename
(DAPI + the names after it) and drawn top-right on each panel in the channel color on a black box.

## Outputs
**Create PowerPoint** makes the deck. **Export PNGs...** writes one unified figure per included image to a folder you pick
(`<image name>.png`, 3000 x 1688 px, same layout as a slide): title and image name, the full merge with scale bar and ROI box,
and the labelled channel panels with your display windows and ROI crop applied. "Show title" and "Show image name" control the
text at the top.

## Review before building
After loading a folder, click **Review...** to:
- tick/untick which images go in the deck,
- set min/max display sliders per channel (Lock freezes a channel and protects it from "Apply windows to all"),
- hide a channel (it is removed from the slide and the merge),
- drag a square ROI on the merge: the slide keeps the full merge with a box drawn on it and the channel panels show only the ROI.

If a sample has any window change or hidden channel, its merge is rebuilt by adding the adjusted channels, so it can differ
slightly from the scope's own merge. Untouched samples use the original merge file. The sliders work on the exported 8-bit
pixels. Settings are not saved between sessions.

The scale bar (merge only) uses `um/pixel` from the sidecar `.txt` in each `.tif.frames` folder; no bar if it is missing.

Assumes channel order in the filename matches C001-C004. Folders with no merged `_T001.tif` are skipped.

## Run from source
    pip install -r requirements.txt
    python app.py

## Build a standalone app (build on each OS you need)
    pip install pyinstaller
    pyinstaller --windowed --name ConfocalDeck --collect-all tkinterdnd2 app.py

Mac: `dist/ConfocalDeck.app`. Windows: `dist/ConfocalDeck/ConfocalDeck.exe`.
Or push this folder to GitHub and run the "Build apps" workflow to get both.

Tests: `pip install -r requirements-dev.txt && pytest`.

Formatting lives in `core.py` (`CHANNEL_COLORS`, `_label`, `build_deck`).
