import unittest

from src.services.family_link_service import (
    LINK_CODE_ALPHABET,
    generate_link_code,
    hash_link_code,
    normalize_link_code,
)


class FamilyLinkServiceTest(unittest.TestCase):
    def test_generated_code_is_human_friendly(self):
        code = generate_link_code()

        self.assertEqual(len(code), 8)
        self.assertTrue(set(code).issubset(set(LINK_CODE_ALPHABET)))

    def test_code_normalization_accepts_spaces_and_lowercase(self):
        self.assertEqual(normalize_link_code("ab23 cd45"), "AB23CD45")

    def test_hash_is_stable_after_normalization(self):
        self.assertEqual(
            hash_link_code("AB23CD45"),
            hash_link_code("ab23 cd45"),
        )

    def test_invalid_code_is_rejected(self):
        with self.assertRaises(ValueError):
            hash_link_code("short")


if __name__ == "__main__":
    unittest.main()
