# This file is what makes `python -m tp_drawer ...` work. When you run a
# package with `-m`, Python looks specifically for a file named
# __main__.py inside it and runs that -- this file's whole job is to hand
# off to the real command-line logic in cli.py.
import sys

from tp_drawer.cli import main

# The `if __name__ == "__main__":` check is a very common Python idiom.
# Every module has a built-in __name__ variable; it's only set to the
# literal string "__main__" when that file is the one being *run*
# directly (as opposed to being imported by something else). So this line
# means "only call main() when this file is actually being executed as
# the program's entry point" -- if some other code ever did
# `import tp_drawer.__main__`, this block would be skipped rather than
# accidentally re-running the whole CLI.
if __name__ == "__main__":
    # sys.exit(main()) passes main()'s return value out as the process's
    # exit code -- 0 means success, non-zero means something went wrong.
    # This is how a shell script or another program calling this tool can
    # tell whether it succeeded without having to scrape the printed text.
    sys.exit(main())
