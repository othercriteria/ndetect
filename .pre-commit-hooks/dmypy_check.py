#!/usr/bin/env python3
import os
import subprocess
import sys


def main():
    # Get the path to system dmypy
    dmypy_path = os.environ.get("DMYPY", "dmypy")

    try:
        # Run dmypy check
        result = subprocess.run(
            [dmypy_path, "check", "."], capture_output=True, text=True
        )

        # Print any output
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(result.stderr, file=sys.stderr)

        return result.returncode

    except FileNotFoundError:
        print("Error: dmypy not found in PATH", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
