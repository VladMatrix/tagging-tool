import argparse

from image_tagging_tool import ImageTaggingTool
from constants import __VERSION__
import sys
import traceback
from datetime import datetime


def log_exceptions(exc_type, exc_value, exc_traceback):
    # Write exception details to a log file with a timestamp
    with open(f"crash_{datetime.now()}.log", "a") as log_file:
        log_file.write(f"VERSION: {__VERSION__}\nUncaught exception:\n")
        traceback.print_exception(exc_type, exc_value, exc_traceback, file=log_file)


if "__main__" == __name__:
    sys.excepthook = log_exceptions
    parser = argparse.ArgumentParser()
    parser.add_argument("--small-window", action="store_true", help="Force the window to small size.")
    parser.add_argument("--tiny-window", action="store_true", help="Force the window to tiny size.")
    args = parser.parse_args()

    if args.tiny_window and args.small_window:
        raise RuntimeError("Only one of --tiny-window or --small-window can be used.")

    ImageTaggingTool(args.small_window, args.tiny_window)
