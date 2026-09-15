"""Builds Appendix B (the photo gallery) from a folder of uploaded site
photos, matching them to trial pits by filename and resizing/compressing
each one to fit the appendix template's own photo boxes.

WHAT THIS DOES AND DOESN'T DO:
This module only understands two things about a filename: whether it
names a trial pit's "Dug" or "Spoils" photo (by containing "TP<number>"
plus "Dug" or "Spoils", case-insensitively, anywhere in it), and, if not,
that it's some other site photo, added as an "extra" with no further
attempt to guess what it shows. Every photo -- Dug/Spoils or extra --
gets the same caption shape: "Photo <n> - <its own filename, minus the
extension>.", "<n>" numbered sequentially in gallery order and bold, the
filename plain -- so an extra photo's caption is exactly as informative
as whatever it was named, which is a deliberate simplification (confirmed
with the user) rather than a keyword dictionary of known extra photo
types: the engineer is expected to tidy up captions by hand afterward
regardless.

Resizing targets the exact photo box sizes measured from the appendix
template itself (see LANDSCAPE_BOX_IN/PORTRAIT_BOX_IN below) -- aspect
ratio is always preserved (fit-within, never cropped), and orientation is
decided from the photo's own pixel dimensions after correcting for EXIF
rotation (phone cameras routinely tag a photo as needing 90-degree
rotation rather than actually storing it pre-rotated).

LAYOUT: the title page never carries any photos, and every page after it
holds up to 4 (a small 2-row, 2-column table, a hard page break before
the next one) -- a deliberate, simple, fixed layout (confirmed with the
user) rather than letting Word's natural table flow decide how many rows
fit per page, which is what caused a real bug once already (the source
template's own leftover blank spacer paragraphs pushed each row onto its
own near-empty page). PitPhotoPage/ExtraPhotoPage below are exactly that
pagination, built once here rather than left to the template.
"""

import re
from dataclasses import dataclass
from pathlib import Path

from docxtpl import DocxTemplate, InlineImage
from docx.shared import Inches
from PIL import Image, ImageOps

from tp_drawer.models import Project

DEFAULT_APPENDIX_B_TEMPLATE_PATH = Path(__file__).resolve().parent.parent / "data" / "appendix_b_template.docx"

# Measured directly from the appendix template's own embedded example
# photos: every landscape photo displays at 3.312"x2.500", the one
# portrait photo at 2.500"x3.328" -- i.e. the same ~2.5"x3.3" box, long
# edge oriented to match the source photo.
LANDSCAPE_BOX_IN = (3.31, 2.50)
PORTRAIT_BOX_IN = (2.50, 3.33)
# Output resolution for the resized copy -- print-reasonable without
# ballooning file size (the template's own example photos, already
# resized/compressed by hand, land in roughly this same size range at a
# comparable resolution).
TARGET_DPI = 150
JPEG_QUALITY = 85

_PIT_NUMBER_RE = re.compile(r"tp\s*0*(\d+)", re.IGNORECASE)
_DUG_RE = re.compile(r"dug", re.IGNORECASE)
_SPOILS_RE = re.compile(r"spoils?", re.IGNORECASE)

_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tif", ".tiff", ".webp", ".heic"}


def is_image_file(path: Path) -> bool:
    return path.suffix.lower() in _IMAGE_SUFFIXES


@dataclass
class _Classified:
    path: Path
    pit_number: int | None  # None if this isn't a recognised Dug/Spoils shot
    kind: str | None  # "dug" | "spoils" | None


def _classify(path: Path) -> _Classified:
    match = _PIT_NUMBER_RE.search(path.stem)
    if match is None:
        return _Classified(path, None, None)
    if _DUG_RE.search(path.stem):
        return _Classified(path, int(match.group(1)), "dug")
    if _SPOILS_RE.search(path.stem):
        return _Classified(path, int(match.group(1)), "spoils")
    return _Classified(path, None, None)


def prepare_image(source_path: Path, dest_path: Path) -> tuple[float, float]:
    """Resize+compress one photo to fit Appendix B's photo box, saved as a
    JPEG at dest_path. Returns (width_in, height_in) -- the exact display
    size to pass to docxtpl's InlineImage, so the embedded picture is
    never stretched/distorted relative to what was actually resized here.
    """
    image = Image.open(source_path)
    # exif_transpose bakes a phone photo's rotation metadata into the
    # actual pixel data -- without this, a photo shot in portrait but
    # tagged "rotate 90" would be (mis)classified as landscape here even
    # though it displays upright and portrait-shaped everywhere else.
    image = ImageOps.exif_transpose(image)
    image = image.convert("RGB")
    native_w, native_h = image.size
    landscape = native_w >= native_h
    box_w_in, box_h_in = LANDSCAPE_BOX_IN if landscape else PORTRAIT_BOX_IN

    native_aspect = native_w / native_h
    box_aspect = box_w_in / box_h_in
    if native_aspect > box_aspect:
        out_w_in, out_h_in = box_w_in, box_w_in / native_aspect
    else:
        out_w_in, out_h_in = box_h_in * native_aspect, box_h_in

    out_w_px = max(1, round(out_w_in * TARGET_DPI))
    out_h_px = max(1, round(out_h_in * TARGET_DPI))
    image = image.resize((out_w_px, out_h_px), Image.LANCZOS)

    dest_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(dest_path, "JPEG", quality=JPEG_QUALITY, optimize=True)
    return out_w_in, out_h_in


def _inline_image(tpl: DocxTemplate, source_path: Path, processed_dir: Path) -> InlineImage:
    dest_path = processed_dir / (source_path.stem + ".jpg")
    width_in, height_in = prepare_image(source_path, dest_path)
    return InlineImage(tpl, str(dest_path), width=Inches(width_in), height=Inches(height_in))


@dataclass
class PitPhotos:
    """One row of Appendix B's per-pit loop. dug_photo/spoils_photo are
    None when no matching file was uploaded for that pit -- the caption
    fields are then both "" (see _caption_parts), rendering as a blank
    photo area with no caption either, so there's nothing dangling like
    "Photo 3 - " with no filename to follow it.

    Each caption is split into two fields, not one, because "Photo N"
    renders bold and " - filename" doesn't -- the template puts each in
    its own run (see build_appendix_templates.py's _tag_caption_cell)
    rather than trying to mark up bold/non-bold spans within one string."""

    dug_photo: InlineImage | None
    dug_caption_number: str
    dug_caption_rest: str
    spoils_photo: InlineImage | None
    spoils_caption_number: str
    spoils_caption_rest: str


@dataclass
class ExtraPhoto:
    photo: InlineImage
    caption_number: str
    caption_rest: str


@dataclass
class ExtraPhotoRow:
    left: ExtraPhoto | None
    right: ExtraPhoto | None


@dataclass
class PitPhotoPage:
    """One page's worth of pit photos -- up to 2 pits (4 photos: each
    pit's Dug + Spoils), per the user's simplified layout rule ("up to 4
    photos per table per page"). row2 is None on a page left with only
    one pit (an odd total pit count's last page)."""

    row1: PitPhotos
    row2: PitPhotos | None


@dataclass
class ExtraPhotoPage:
    """Same page-of-up-to-4-photos rule as PitPhotoPage, but for the
    extra-photos section: each ExtraPhotoRow already holds up to 2
    photos, so a page holds up to 2 of those rows. row2 is None on a page
    left with only one row."""

    row1: ExtraPhotoRow
    row2: ExtraPhotoRow | None


def _paginate(items: list, page_cls):
    """Groups `items` into pages of at most 2, wrapped as `page_cls(row1,
    row2)` -- shared chunking behind both PitPhotoPage and
    ExtraPhotoPage, since "up to 4 photos per page" means the same "2
    row-things per page" rule either way (a PitPhotos row IS 2 photos;
    an ExtraPhotoRow already IS 2 photos)."""
    return [page_cls(row1=items[i], row2=items[i + 1] if i + 1 < len(items) else None) for i in range(0, len(items), 2)]


def build_appendix_b_context(project: Project, photo_dir: Path, tpl: DocxTemplate) -> dict:
    """Matches every image file in `photo_dir` to a pit's Dug/Spoils slot
    or, failing that, treats it as an extra site photo -- then resizes,
    compresses, and wraps each one as a docxtpl InlineImage (processed
    copies are written to photo_dir/_processed/, alongside the originals).
    Returns just the two context keys Appendix B's template loops need;
    the caller merges this with the same project_number/report_date_numeric
    context every appendix shares (see report_io.build_report_context)."""
    processed_dir = photo_dir / "_processed"
    if not photo_dir.is_dir():
        # No photos uploaded for this job yet -- every pit's Dug/Spoils
        # slot renders blank rather than this raising on a missing folder.
        files = []
    else:
        # Directory listing order stands in for upload order -- good
        # enough given the filename-driven matching does the real work;
        # see module docstring on why perfect upload-order fidelity isn't
        # the goal here. Excludes the _processed/ subfolder itself (a
        # directory, so it fails is_file()) where resized copies land.
        files = sorted(p for p in photo_dir.iterdir() if p.is_file() and is_image_file(p))

    dug_by_pit: dict[int, Path] = {}
    spoils_by_pit: dict[int, Path] = {}
    extras: list[Path] = []
    for path in files:
        classified = _classify(path)
        if classified.kind == "dug" and classified.pit_number not in dug_by_pit:
            dug_by_pit[classified.pit_number] = path
        elif classified.kind == "spoils" and classified.pit_number not in spoils_by_pit:
            spoils_by_pit[classified.pit_number] = path
        else:
            extras.append(path)

    def _pit_number(pit) -> int | None:
        try:
            return int(pit.number)
        except ValueError:
            return None

    # Every photo is numbered "Photo 1", "Photo 2", ... in gallery order:
    # each pit's Dug then Spoils (a missing slot contributes nothing --
    # there's no filename to number), then the extras in file order. This
    # numbering is assigned once, up front, against the whole ordered
    # list, rather than per-loop in the template, since the pit-photos and
    # extra-photos sections are two separate {%p for %} loops (each page a
    # fixed 2-row table -- see build_appendix_templates.py) with no shared
    # counter of their own.
    ordered_paths: list[Path] = []
    for pit in project.pits:
        pit_number = _pit_number(pit)
        if pit_number in dug_by_pit:
            ordered_paths.append(dug_by_pit[pit_number])
        if pit_number in spoils_by_pit:
            ordered_paths.append(spoils_by_pit[pit_number])
    ordered_paths.extend(extras)
    photo_index = {path: i + 1 for i, path in enumerate(ordered_paths)}

    def _caption_parts(path: Path | None) -> tuple[str, str]:
        if path is None:
            return "", ""
        return f"Photo {photo_index[path]}", f" - {path.stem}."

    photo_pits = []
    for pit in project.pits:
        pit_number = _pit_number(pit)
        dug_path = dug_by_pit.get(pit_number)
        spoils_path = spoils_by_pit.get(pit_number)
        dug_number, dug_rest = _caption_parts(dug_path)
        spoils_number, spoils_rest = _caption_parts(spoils_path)
        photo_pits.append(
            PitPhotos(
                dug_photo=_inline_image(tpl, dug_path, processed_dir) if dug_path else None,
                dug_caption_number=dug_number,
                dug_caption_rest=dug_rest,
                spoils_photo=_inline_image(tpl, spoils_path, processed_dir) if spoils_path else None,
                spoils_caption_number=spoils_number,
                spoils_caption_rest=spoils_rest,
            )
        )

    extra_photos = []
    for path in extras:
        number, rest = _caption_parts(path)
        extra_photos.append(ExtraPhoto(photo=_inline_image(tpl, path, processed_dir), caption_number=number, caption_rest=rest))
    extra_photo_rows = [
        ExtraPhotoRow(left=extra_photos[i], right=extra_photos[i + 1] if i + 1 < len(extra_photos) else None)
        for i in range(0, len(extra_photos), 2)
    ]

    return {
        "pit_pages": _paginate(photo_pits, PitPhotoPage),
        "extra_pages": _paginate(extra_photo_rows, ExtraPhotoPage),
        "has_extras": bool(extra_photo_rows),
    }


def generate_appendix_b(
    project: Project,
    photo_dir: Path,
    base_context: dict,
    output_path: str | Path,
    template_path: str | Path = DEFAULT_APPENDIX_B_TEMPLATE_PATH,
) -> None:
    """Renders Appendix B for `project`, using whatever photos are
    present in `photo_dir` (none at all is fine -- every pit's Dug/Spoils
    slots just render blank). `base_context` supplies the header fields
    every appendix shares (project_number, report_date_numeric --
    normally report_io.build_report_context's own output).

    autoescape=True -- see report_io.render_docx_template's docstring for
    why this is required (a raw "&" in, e.g., project_title_line
    otherwise produces invalid XML and crashes the render); harmless here
    for the same reason it's harmless there -- InlineImage defines
    __html__ so Jinja2 never tries to escape an actual photo."""
    tpl = DocxTemplate(template_path)
    context = {**base_context, **build_appendix_b_context(project, photo_dir, tpl)}
    tpl.render(context, autoescape=True)
    tpl.save(output_path)
