import importlib
import sys
import unittest
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVER_DIR))

import model_registry  # noqa: E402


class V11ProfilesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        model_registry._purge_core()
        model_registry._register_core(SERVER_DIR / "models" / "V11")
        cls.adapter = importlib.import_module("core.adapter")
        cls.lookup = cls.adapter._profile_lookup()

    def test_uk_profile_is_available_and_mapped_to_supported_type(self):
        self.assertIn("UB305*165*46", self.lookup.index)
        row = self.lookup.loc["UB305*165*46"]
        self.assertEqual(row["type"], "W")
        self.assertGreater(float(row["d_mm"]), 0)

    def test_unsupported_uk_sections_are_excluded(self):
        for prefix in ("PFC", "UPE", "UPN", "RSA", "TEE"):
            self.assertFalse(
                any(name.startswith(prefix) for name in self.lookup.index),
                f"{prefix} no deberia ofrecerse en V11",
            )


if __name__ == "__main__":
    unittest.main()
