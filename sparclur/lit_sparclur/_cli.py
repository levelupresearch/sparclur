"""Console entry point for the packaged Streamlit interface."""

from pathlib import Path
import sys


def _streamlit_main():
    """Import Streamlit only when the optional UI command is invoked."""
    from streamlit.web.cli import main

    return main()


def main():
    """Launch Lit Sparclur and forward any arguments to Streamlit."""
    try:
        streamlit_main = _streamlit_main()
    except ImportError:
        print(
            "The Sparclur UI requires Streamlit. Install it with: pip install 'sparclur[ui]'",
            file=sys.stderr,
        )
        return 1

    app_path = Path(__file__).with_name("lit_sparclur.py")
    original_argv = sys.argv
    try:
        sys.argv = [sys.argv[0], "run", str(app_path), *original_argv[1:]]
        return streamlit_main()
    finally:
        sys.argv = original_argv
