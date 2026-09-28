"""One turn up close; see edhkit/turnview.py.

    python3 research/turn_view.py <sim-out> <game> <turn> [--deck deck.txt]
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from edhkit.turnview import main  # noqa: E402

if __name__ == "__main__":
    main()
