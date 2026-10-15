import unittest
from types import SimpleNamespace
from tools import calculator, execute


class CalculatorTests(unittest.TestCase):
    def test_arithmetic(self):
        self.assertEqual(calculator("(12+3)*4"), 60)
        self.assertEqual(calculator("-2**2"), -4)
        self.assertEqual(calculator("1/4"), 0.25)

    def test_reject_code_and_resource_abuse(self):
        for expression in ["__import__('os').system('id')", "2**99999", "True", "[1]*100", "1e999", "3j"]:
            with self.subTest(expression=expression), self.assertRaises((ValueError, SyntaxError)):
                calculator(expression)

    def test_bad_arguments_are_observations(self):
        for name, args in [("other", "{}"), ("calculator", "null"), ("calculator", "{bad"),
                           ("calculator", '{"expression":"1/0"}'),
                           ("calculator", '{"expression":"1","extra":1}')]:
            call = SimpleNamespace(function=SimpleNamespace(name=name, arguments=args))
            self.assertFalse(execute(call)["ok"])


if __name__ == "__main__":
    unittest.main()
