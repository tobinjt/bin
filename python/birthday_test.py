import decimal
import unittest
from unittest import mock

import birthday


class TestBirthday(unittest.TestCase):
    """Tests for birthday."""

    def test_birthday(self):
        """Test cases for birthday."""
        # With 23 people, the probability is > 50%
        self.assertGreater(birthday.birthday(23, 365), decimal.Decimal("0.5"))
        # With 366 people, the probability is 1.
        self.assertEqual(birthday.birthday(366, 365), decimal.Decimal("1"))
        # With 1 person, the probability is 0.
        self.assertEqual(birthday.birthday(1, 365), decimal.Decimal("0"))


class TestMain(unittest.TestCase):
    """Tests for main."""

    @mock.patch.object(birthday, "birthday")
    def test_main(self, mock_birthday):
        """Test cases for main."""
        birthday.main(["birthday.py", "23"])
        mock_birthday.assert_called_with(23, 365)

        birthday.main(["birthday.py", "23", "366"])
        mock_birthday.assert_called_with(23, 366)

    def test_main_errors(self):
        """Test error cases for main."""
        with self.assertRaises(SystemExit) as cm:
            birthday.main(["birthday.py"])
        self.assertEqual(cm.exception.code, "Usage: birthday.py NUM_PEOPLE [NUM_DAYS]")

        with self.assertRaises(SystemExit) as cm:
            birthday.main(["birthday.py", "foo"])
        self.assertEqual(cm.exception.code, "Argument is not a number: foo")

        with self.assertRaises(SystemExit) as cm:
            birthday.main(["birthday.py", "1", "bar"])
        self.assertEqual(cm.exception.code, "Argument is not a number: bar")

        with self.assertRaises(SystemExit) as cm:
            birthday.main(["birthday.py", "0"])
        self.assertEqual(
            cm.exception.code, "Number of people must be greater than 0: 0"
        )

        with self.assertRaises(SystemExit) as cm:
            birthday.main(["birthday.py", "1", "0"])
        self.assertEqual(cm.exception.code, "Number of days must be greater than 0: 0")


if __name__ == "__main__":
    unittest.main()
