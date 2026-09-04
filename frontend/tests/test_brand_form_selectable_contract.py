#!/usr/bin/env python3

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PAGE = ROOT / "frontend/app/brands/page.tsx"
CSS = ROOT / "frontend/app/globals.css"


class BrandFormSelectableContract(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.page = PAGE.read_text()
        cls.css = CSS.read_text()

    def test_only_brand_name_is_required(self):
        self.assertEqual(
            len(
                re.findall(
                    r"<input\s+required\b",
                    self.page,
                )
            ),
            1,
        )
        self.assertIn(
            "只有品牌名稱必填",
            self.page,
        )

    def test_quick_fields_have_selectable_options(self):
        for option_id in (
            "industry-options",
            "country-options",
            "language-options",
            "tone-options",
            "cta-options",
        ):
            self.assertIn(
                f'<datalist id="{option_id}">',
                self.page,
            )
            self.assertIn(
                f'list="{option_id}"',
                self.page,
            )

    def test_options_still_allow_custom_input(self):
        self.assertIn(
            "可從選項挑選或自行輸入",
            self.page,
        )

    def test_advanced_fields_are_optional(self):
        self.assertIn(
            "showAdvanced",
            self.page,
        )
        self.assertIn(
            'aria-expanded={showAdvanced}',
            self.page,
        )
        self.assertIn(
            "進階設定（選填）",
            self.page,
        )

        self.assertEqual(
            self.page.count(
                "brand-advanced-field"
            ),
            9,
        )

    def test_existing_api_payload_fields_remain(self):
        for field in (
            "name",
            "industry",
            "website",
            "description",
            "tone",
            "target_audience",
            "brand_voice",
            "value_proposition",
            "products_services",
            "keywords",
            "forbidden_words",
            "default_cta",
            "language",
            "country",
            "brand_guidelines",
        ):
            self.assertIn(
                f"form.{field}",
                self.page,
            )

    def test_optional_field_css_exists(self):
        self.assertIn(
            ".brand-form-intro",
            self.css,
        )
        self.assertIn(
            ".brand-advanced-field.is-visible",
            self.css,
        )


if __name__ == "__main__":
    unittest.main()
