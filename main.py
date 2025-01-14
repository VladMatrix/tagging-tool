import argparse

from image_tagging_tool import ImageTaggingTool
import sys
import traceback
from datetime import datetime


__VERSION__ = "1.0.1-rc"


def log_exceptions(exc_type, exc_value, exc_traceback):
    # Write exception details to a log file with a timestamp
    with open(f"crash_{datetime.now()}.log", "a") as log_file:
        log_file.write(f"VERSION: {__VERSION__}\nUncaught exception:\n")
        traceback.print_exception(exc_type, exc_value, exc_traceback, file=log_file)


if "__main__" == __name__:
    sys.excepthook = log_exceptions
    parser = argparse.ArgumentParser()
    parser.add_argument("--small-window", action="store_true", help="Force the window to small size.")
    args = parser.parse_args()
    ImageTaggingTool(args.small_window)
