import tempfile
import unittest
from pathlib import Path

from compiler.moss import MossError, compile_source

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"


class SemanticValidationTests(unittest.TestCase):
    def compile_text(self, source):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "test.moss"
            path.write_text(source)
            return compile_source(path)

    def test_bare_word_output_must_be_defined_or_quoted(self):
        with self.assertRaises(MossError) as err:
            self.compile_text("fn main\n    output hi\n")

        message = err.exception.format()
        self.assertIn('Moss found "hi"', message)
        self.assertIn('If you meant text, put it in quotes: "hi"', message)

    def test_quoted_output_is_text_not_variable(self):
        rust = self.compile_text('fn main\n    output "hi"\n')

        self.assertIn('Value::String(String::from("hi"))', rust)

    def test_function_body_cannot_see_main_variables(self):
        with self.assertRaises(MossError) as err:
            self.compile_text(
                "fn greet\n"
                "    return name\n"
                "\n"
                "fn main\n"
                "    name = \"ada\"\n"
                "    output greet()\n"
            )

        self.assertIn('Moss found "name"', err.exception.format())


class InvalidFixtureTests(unittest.TestCase):
    def test_invalid_fixtures_match_expected_diagnostics(self):
        for source_path in sorted((FIXTURES / "invalid").glob("*.moss")):
            with self.subTest(source=source_path.name):
                expected_path = source_path.with_suffix(".stderr")
                expected_lines = expected_path.read_text().splitlines()

                with self.assertRaises(MossError) as err:
                    compile_source(source_path)

                message = err.exception.format()
                for expected in expected_lines:
                    self.assertIn(expected, message)
                self.assertNotIn("error[E", message)


if __name__ == "__main__":
    unittest.main()
