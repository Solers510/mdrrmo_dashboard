import unittest

from services.validation_service import (
    ValidationInputError,
    validate_review_decision,
)


class ValidationDecisionTests(unittest.TestCase):
    def test_validated_may_have_no_notes(self):
        self.assertIsNone(
            validate_review_decision(
                decision="Validated",
                review_notes="",
            )
        )

    def test_correction_requires_instructions(self):
        with self.assertRaises(ValidationInputError):
            validate_review_decision(
                decision="Needs Correction",
                review_notes="  ",
            )

    def test_correction_notes_are_trimmed(self):
        self.assertEqual(
            validate_review_decision(
                decision="Needs Correction",
                review_notes="  Correct family count.  ",
            ),
            "Correct family count.",
        )

    def test_invalid_decision_rejected(self):
        with self.assertRaises(ValidationInputError):
            validate_review_decision(
                decision="Approved",
                review_notes=None,
            )


if __name__ == "__main__":
    unittest.main()
