import json
import unittest
from pathlib import Path

from test.common import BASE_DIR

_LANG_SERVER_DIR = BASE_DIR / "langserver"
_MULTI_SERVER_DIR = BASE_DIR / "multiserver"


class LangServerJson(unittest.TestCase):
    def test_json_content(self) -> None:
        def _check_json(p: Path) -> None:
            with open(p, "r", encoding="utf-8") as f:
                json.load(f)

        for d in (_LANG_SERVER_DIR, _MULTI_SERVER_DIR):
            for f in d.iterdir():
                if f.is_file() and f.suffix == ".json":
                    with self.subTest(file=f):
                        _check_json(f)
