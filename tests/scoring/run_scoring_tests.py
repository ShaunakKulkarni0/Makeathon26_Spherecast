from __future__ import annotations

import pathlib
import sys
import unittest


def main() -> int:
    test_dir = pathlib.Path(__file__).parent
    project_root = test_dir.parent.parent.resolve()
    sys.path.insert(0, str(project_root))

    suite = unittest.defaultTestLoader.discover(
        start_dir=str(test_dir),
        pattern="test_*.py",
        top_level_dir=str(project_root),
    )
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
