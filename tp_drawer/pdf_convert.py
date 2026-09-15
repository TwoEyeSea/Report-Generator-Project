"""Converts a .docx file to PDF via a headless LibreOffice subprocess --
used by the webapp's export feature to offer PDF copies of Appendices A,
C, and D alongside their .docx originals.

WHY LIBREOFFICE, NOT MICROSOFT WORD:
Word can be driven via COM automation (pywin32) to do the same
conversion, but that launches Word's actual GUI application under the
hood, and in practice (confirmed directly against this project's own
templates) has a real chance of hanging indefinitely rather than failing
cleanly. LibreOffice's --headless --convert-to mode runs as a plain,
non-interactive subprocess with no GUI automation involved, and either
finishes or hits the timeout below -- never hangs a live web request the
way the Word alternative did.
"""

import shutil
import subprocess
from pathlib import Path

# Common Windows install locations, tried before falling back to PATH
# (shutil.which) -- a fresh install (e.g. via winget) doesn't always put
# soffice.exe on PATH.
_CANDIDATE_PATHS = (
    r"C:\Program Files\LibreOffice\program\soffice.exe",
    r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
)


class PdfConversionUnavailable(RuntimeError):
    """Raised when no LibreOffice installation can be found at all --
    distinct from a conversion that ran but failed or timed out, so a
    caller can tell "not installed" apart from "something went wrong"."""


def _find_soffice() -> str:
    for path in _CANDIDATE_PATHS:
        if Path(path).is_file():
            return path
    found = shutil.which("soffice")
    if found:
        return found
    raise PdfConversionUnavailable("LibreOffice (soffice) was not found. Install it from libreoffice.org to enable PDF exports.")


def convert_to_pdf(docx_path: str | Path, *, timeout: int = 120) -> Path:
    """Converts `docx_path` to a PDF sitting alongside it (same folder,
    same basename, .pdf extension) and returns that PDF's path.

    `timeout` is a defensive backstop, not the expected case -- a real
    conversion normally takes several seconds -- so a genuine hang still
    fails the request with a clear error instead of hanging it forever,
    unlike the Word COM approach this deliberately avoids (see the
    module docstring)."""
    docx_path = Path(docx_path)
    soffice = _find_soffice()
    subprocess.run(
        [soffice, "--headless", "--convert-to", "pdf", "--outdir", str(docx_path.parent), str(docx_path)],
        check=True,
        capture_output=True,
        timeout=timeout,
    )
    return docx_path.with_suffix(".pdf")
