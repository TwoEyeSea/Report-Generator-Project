# Report generator: fix batch #2 (Notes default, Section 5 highlight, multi-foundation)

Saved as a durable reference (not just Claude's own transient plan-mode file) so this plan survives into a future session. Follows on from fix batch #1 (bold fix, three formation cases, `is_native` field) which has already been implemented.

## Context

The user reviewed the generated report again and has three more items: a smarter default for the Notes section, a visual "review me" cue on the Conclusion section, and support for recommending more than one foundation system.

Confirmed decisions (asked via AskUserQuestion, all recommended options accepted):
- Divergent per-pit notes render as dash-bulleted lines under a "Notes:" heading, matching the new default's style — not the old single combined sentence.
- The yellow highlight covers the *whole* Conclusion section: the "CONCLUSION" heading, its intro paragraph, and the entire foundation subsection(s) below it.
- The "5.1"/"5.2" foundation subheading numbers switch from hand-typed text to a real Word multilevel-list auto-number field (same mechanism `"1.1 Site Work"` already uses) — this is the actual fix for the fragility that broke last time the report was restructured, and it's what makes an arbitrary number of "Option N" subsections (5.1, 5.2, 5.3, ...) work for free instead of needing hardcoded number logic in Python.

**Verified during planning (read-only prototyping in `scratch/`, not part of this plan's implementation):**
- Nested `{%p for %}` loops work correctly in docxtpl (built and rendered a minimal two-level test template) — needed because each foundation option now needs its own nested loop of paragraph text within an outer loop over however many options were recommended.
- `numId=44`'s level-1 format is `%1.%2` (confirmed in fix batch #1) — a paragraph carrying `<w:numPr><w:ilvl w:val="1"/><w:numId w:val="44"/></w:numPr>` under the "CONCLUSION" (level 0) heading will render as "5.1", and repeated sibling paragraphs at that level auto-increment ("5.1", "5.2", ...) regardless of how they were generated, since OOXML numbering is computed from final document structure, not paragraph history.

## Changes

### 1. Notes section (Section 3.1) default + divergent formatting

`tp_drawer/report_io.py`'s `_notes_context`: replace the current `notes_label`/`notes_text` pair with `notes_heading: str` (bold lead-in) and `notes_lines: list[str]` (each an already-dash-prefixed line):
- No pit has a non-empty note → `notes_heading="All Tps:"`, `notes_lines=["- Excavated successfully"]` (the new default, replacing today's plain "None.").
- Every pit's note is present and identical → `notes_heading="All Tps:"`, `notes_lines=["- " + that text]`.
- Otherwise (any divergence, or some pits blank and others not) → `notes_heading="Notes:"`, `notes_lines=[f"- TP{number}: {text}" for each pit with a non-empty note]`.

`scripts/build_report_template.py`: the Notes section currently has two fixed paragraphs (`{{ notes_label }}` heading, `{{ notes_text }}` body). Restructure the body paragraph into a `{%p for line in notes_lines %}` / `{{ line }}` / `{%p endfor %}` loop (same pattern already used for Soil Descriptions and foundation paragraphs), so it renders 1 or more bulleted lines instead of exactly one.

### 2. Yellow highlight on the whole Conclusion section (Section 5.0)

`scripts/build_report_template.py`: after tagging, set `run.font.highlight_color = WD_COLOR_INDEX.YELLOW` (`from docx.enum.text import WD_COLOR_INDEX`) on every run in:
- The "CONCLUSION" heading paragraph.
- The Conclusion intro paragraph's run (the one templated with `{{ primary_formation }}`).
- The foundation section's heading loop-body paragraph's run, and the plain-paragraphs / list-paragraphs inner loop-body runs (see below) — since docxtpl clones a loop body's raw XML per iteration, highlighting the loop-body run once makes every rendered instance yellow, however many foundation options end up being generated.

This does *not* cover the appendix-references line, signature block, or "I trust this information..." closing paragraphs that follow — those aren't part of Section 5.0's own content.

### 3. Multiple recommended foundations (Section 5.1 / 5.2 / ...)

**Data model — `tp_drawer/models.py` / `tp_drawer/excel_io.py`:**
- Rename `ProjectInfo.recommended_foundation: str` → `recommended_foundations: list[str] = field(default_factory=list)`.
- `excel_io.py`: replace the single `"option 1"` entry in `_TRAILING_OPTIONAL_ALIASES` with an open-ended scan (mirroring the existing "don't hardcode a count" philosophy used for pit columns/layer rows elsewhere in this file) that collects every non-blank `"option N"` row's value, in order, into `info.recommended_foundations`. Today's sample sheet has "Option 1: Strip Footings" / "Option 2: " (blank) → yields `["Strip Footings"]`; a sheet with both filled in yields two entries.
- `project_from_dict` (`models.py`): currently does `ProjectInfo(**data["info"])` with no filtering — an old saved `project.json` still carrying the removed `recommended_foundation` key would crash with an unexpected-keyword `TypeError`. Fix by filtering `data["info"]` down to `ProjectInfo`'s actual field names before unpacking (a small, generally-useful robustness fix, not just a workaround for this one rename).

**`tp_drawer/report_io.py`'s `_foundation_context`:** rebuild to return `foundation_sections: list[FoundationSection]` (a small new dataclass: `heading_text`, `plain_paragraphs`, `list_paragraphs`), one per name in `recommended_foundations` that matches a catalog entry (unmatched names get the existing "no stored write-up" placeholder as their own section, same graceful-degradation pattern as today). Heading text:
- Exactly one total recommended foundation → `"Recommended Foundation: {name}"` (matches today's wording — this is case (a), unchanged in appearance).
- Two or more → `"Option {i+1} - {name}"` for each (case (b)).
- Zero recommended (sheet had nothing filled in) → a single placeholder section, same spirit as today's "[foundation type not specified]".

**`scripts/build_report_template.py`:** restructure the foundation block from today's single heading + two loops into a doubly-nested loop:
- Outer: `{%p for section in foundation_sections %}` ... `{%p endfor %}`.
- Inside: one heading paragraph — strip its current hand-typed `"5"`, `".1 "`, `"\t"` runs entirely and give it `<w:numPr><w:ilvl w:val="1"/><w:numId w:val="44"/></w:numPr>` (built via `OxmlElement`, since this paragraph has no existing `numPr` to edit) so Word's own list engine supplies the visible "5.1"/"5.2"/... prefix; its text becomes `{{ section.heading_text }}`.
- Then a nested `{%p for para in section.plain_paragraphs %}{{ para }}{%p endfor %}` block (reusing the existing plain-paragraph loop body paragraph).
- Then a nested `{%p for para in section.list_paragraphs %}{{ para }}{%p endfor %}` block (reusing the existing numbered-list loop body paragraph, `numId=32` list styling untouched).

`tp_drawer/catalog.py`'s `FoundationOption` is unchanged — this is purely a report_io.py/template concern; the catalog still just stores one option's name + paragraphs, same as today.

## Files touched
- `tp_drawer/report_io.py` (`_notes_context`, `_foundation_context` + new `FoundationSection` dataclass)
- `scripts/build_report_template.py` (Notes loop restructure, yellow highlight pass, foundation double-loop + real auto-numbering)
- `data/report_template.docx` (regenerated by running the script)
- `tp_drawer/models.py` (`ProjectInfo.recommended_foundations`, `project_from_dict` field-filtering)
- `tp_drawer/excel_io.py` (open-ended "option N" scan replacing the single "option 1" alias)

## Verification
1. Re-run `python scripts/build_report_template.py`; dump the resulting template's paragraphs to confirm the Notes loop, the yellow-highlighted runs (`run.font.highlight_color`), and the foundation heading's new `numPr`.
2. Build synthetic `Project` fixtures covering: no notes / identical notes / divergent notes; zero / one / two recommended foundations (including one unmatched name); confirm `build_report_context` produces the expected `notes_heading`/`notes_lines` and `foundation_sections` shapes.
3. Generate real `.docx` output for a two-foundation case and confirm (via python-docx) two separate heading paragraphs both carry the new `numPr` at `ilvl=1, numId=44`, and that the highlighted runs are present — actual "5.1"/"5.2" number rendering can only be fully confirmed by opening in real Word, which isn't available here, so call this out explicitly rather than claim it's visually verified.
4. Run the full `pytest` suite (expect the same single pre-existing, unrelated hatch-pattern failure).
5. Re-run the generate → edit → download-report flow through the live web app on a scratch port (never the user's own running instance) as in prior rounds.

## Note on scope
Implementation of these three items is deferred to a later session at the user's request — this document is the only output of this planning round.
