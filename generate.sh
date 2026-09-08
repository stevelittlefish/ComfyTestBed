#!/usr/bin/env bash
# Fire prompts at the render core. Wraps run.py so you don't have to remember it.
#
#   ./generate.sh                        # generate every combo not yet in the can
#   ./generate.sh --list                 # show the plan, generate nothing
#   ./generate.sh --force                # regenerate everything (careful, Captain)
#   ./generate.sh -w SDXL                # only one workflow
#   ./generate.sh -w SDXL -w flux_dev    # several (repeat -w)
#
# Any arguments are passed straight through to run.py.
set -euo pipefail

cd "$(dirname "$0")"
exec python3 run.py "$@"
