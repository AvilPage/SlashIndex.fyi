# /// script
# requires-python = ">=3.9"
# dependencies = [
#     "csvtotable",
# ]
# ///
"""Generate index.html from slashindex.csv using csvtotable.

https://github.com/vividvilla/csvtotable
"""
import shutil
import subprocess
import sys

CSV_FILE = "slashindex.csv"
HTML_FILE = "index.html"
LINK_JS_FILE = "link-domains.js"


def main():
    subprocess.run(["cottagecrawl", "slashindex"], check=True)
    shutil.copy("/Users/anand/.config/cottagecrawl/slashindex.csv", CSV_FILE)

    csvtotable = shutil.which("csvtotable")
    if not csvtotable:
        sys.exit("csvtotable not found on PATH. Install with: uv tool install csvtotable")

    subprocess.run(
        [
            csvtotable,
            "--overwrite",
            "--title",
            "/Index",
            "--description-html",
            "@description.html",
            "--js",
            LINK_JS_FILE,
            CSV_FILE,
            HTML_FILE,
        ],
        check=True,
    )

    import webbrowser, pathlib
    webbrowser.open(pathlib.Path(HTML_FILE).resolve().as_uri())


if __name__ == "__main__":
    main()