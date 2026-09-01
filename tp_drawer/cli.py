"""Command-line interface: `python -m tp_drawer build|template ...`.

This module wires up the three things you can type after `tp_drawer` on
the command line -- `build`, `template`, and `serve` -- using Python's
built-in argparse library. argparse's job is to turn a raw list of text
strings (what the user typed, e.g. ["build", "input.xlsx", "--debug"])
into a tidy `args` object with named, correctly-typed attributes
(args.input, args.debug, ...), and to automatically generate --help text,
reject bad input with a clear message, etc., so none of that has to be
hand-written here.
"""

import argparse
import sys
from pathlib import Path

from tp_drawer.catalog import hydrate_descriptions, load_catalog
from tp_drawer.config import Config
from tp_drawer.drawing import render_project
from tp_drawer.excel_io import read_project, write_template


def _cmd_build(args: argparse.Namespace) -> int:
    """Runs when the user types `tp_drawer build ...`. Reads the input
    workbook, fills in any missing unit descriptions from the catalog,
    and renders the finished PDF -- the same three-step pipeline the
    webapp's /generate route uses."""
    # If the user didn't pass -o/--output, default to the input filename
    # with its extension swapped for .pdf, e.g. "job.xlsx" -> "job.pdf".
    output = args.output or str(Path(args.input).with_suffix(".pdf"))
    try:
        project = read_project(args.input)
        hydrate_descriptions(project, load_catalog())
        render_project(project, output, Config())
    except (ValueError, FileNotFoundError) as exc:
        # These two exception types cover the "expected" failure modes --
        # a missing file, or a workbook whose contents don't parse (e.g. a
        # depth cell that isn't valid feet-inches text). Anything else
        # (a genuine bug) is deliberately left to propagate as a full
        # traceback rather than being swallowed here.
        if args.debug:
            # --debug re-raises the real exception with its full Python
            # traceback, which is useful when *developing* the tool but
            # far too technical for a normal user just trying to build a
            # log -- hence it's opt-in rather than the default.
            raise
        print(f"Error: {exc}", file=sys.stderr)
        # By convention, a process returns exit code 0 for success and
        # non-zero for failure. Returning 1 here (rather than raising)
        # lets a calling script check `if tp_drawer build ...; then` and
        # react to failure without seeing a scary traceback.
        return 1
    print(f"Wrote {output} ({len(project.pits)} trial pit(s))")
    return 0


def _cmd_template(args: argparse.Namespace) -> int:
    """Runs when the user types `tp_drawer template ...`. Generates a
    blank input .xlsx with the right headers/columns, so a new user has
    something correctly-shaped to fill in rather than building one from
    scratch."""
    # "Topsoil, Peat, Beach Sand" -> ["Topsoil", "Peat", "Beach Sand"];
    # .strip() on each piece trims any stray spaces after the commas
    # (e.g. "Topsoil, Peat" typed with a space after the comma).
    layer_names = tuple(name.strip() for name in args.layers.split(","))
    write_template(args.output, num_pits=args.pits, layer_names=layer_names)
    print(f"Wrote template {args.output}")
    return 0


def _cmd_serve(args: argparse.Namespace) -> int:
    """Runs when the user types `tp_drawer serve ...`. Starts the local
    web app (see webapp/app.py) instead of doing a one-off build."""
    # The import lives inside the function body, not at the top of the
    # file with the others -- this is a "deferred" or "lazy" import.
    # Flask (the web framework) is only needed if you actually run
    # `serve`; someone who only ever runs `build`/`template` shouldn't be
    # forced to have Flask installed at all. Importing it here, only when
    # this function actually runs, keeps that dependency optional.
    from webapp.app import main as run_webapp  # deferred: build/template don't need Flask installed

    print(f"Serving on http://{args.host}:{args.port} (Ctrl+C to stop)")
    run_webapp(host=args.host, port=args.port)
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Declares the full command-line grammar: `build`, `template`, and
    `serve` as subcommands, each with its own arguments. Kept as a
    separate function (rather than inlined into main()) so tests can call
    build_parser() directly and check its behaviour without actually
    running any command."""
    parser = argparse.ArgumentParser(prog="tp_drawer")
    # add_subparsers is what makes `tp_drawer build ...` and
    # `tp_drawer template ...` behave like two different mini-programs
    # sharing one entry point (similar to how `git commit` and `git push`
    # are both "git", just with different sub-grammars). required=True
    # means running bare `tp_drawer` with no subcommand at all is an
    # error, rather than silently doing nothing.
    subparsers = parser.add_subparsers(dest="command", required=True)

    build_p = subparsers.add_parser("build", help="Generate a trial pit log PDF from an input workbook")
    build_p.add_argument("input", help="Path to the input .xlsx workbook")
    build_p.add_argument("-o", "--output", help="Output PDF path (default: input path with .pdf extension)")
    build_p.add_argument("--debug", action="store_true", help="Show full tracebacks on error")
    # set_defaults(func=...) attaches which function should handle this
    # subcommand directly onto the parsed args -- see main() below, where
    # `args.func(args)` calls whichever one was attached. This avoids an
    # if/elif chain like `if args.command == "build": _cmd_build(args)
    # elif args.command == "template": ...` -- each subcommand just
    # carries its own handler along with it.
    build_p.set_defaults(func=_cmd_build)

    template_p = subparsers.add_parser("template", help="Generate a blank input workbook")
    template_p.add_argument("output", help="Path to write the new .xlsx template")
    template_p.add_argument("--pits", type=int, default=4, help="Number of trial pit columns (default: 4)")
    template_p.add_argument(
        "--layers",
        default="Topsoil,Peat,Beach Sand",
        help="Comma-separated layer names, top to bottom (default: Topsoil,Peat,Beach Sand)",
    )
    template_p.set_defaults(func=_cmd_template)

    serve_p = subparsers.add_parser("serve", help="Run the local web app")
    serve_p.add_argument("--host", default="127.0.0.1", help="Host to bind (default: 127.0.0.1)")
    serve_p.add_argument("--port", type=int, default=5000, help="Port to bind (default: 5000)")
    serve_p.set_defaults(func=_cmd_serve)

    return parser


def main(argv: list[str] | None = None) -> int:
    """The single entry point every code path funnels through: the real
    `tp_drawer` command, `python -m tp_drawer` (via __main__.py), and any
    test that wants to simulate a command-line invocation by passing its
    own argv list directly instead of reading sys.argv."""
    parser = build_parser()
    # argv=None makes argparse read the real command-line arguments
    # (sys.argv) automatically -- tests instead pass an explicit list
    # like ["build", "job.xlsx"], letting them exercise the CLI without
    # needing a real subprocess or messing with sys.argv globally.
    args = parser.parse_args(argv)
    # `args.func` is whichever handler set_defaults(func=...) attached
    # above, based on which subcommand was used -- calling it here is
    # what actually runs `build`/`template`/`serve`.
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
