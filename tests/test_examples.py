import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MOSS = ROOT / "moss"

EXAMPLE_OUTPUTS = {
    "01_hello.moss": '"hello, world"\n',
    "02_output_record.moss": '{"type":"ready","ok":true,"count":3}\n',
    "03_nested.moss": (
        '{"type":"user_created","payload":{"name":"ada","age":36,'
        '"skills":{"primary":"math","secondary":"engineering"}}}\n'
    ),
    "04_variables.moss": '{"type":"ready","service":"demo","version":"1.0","port":8080}\n',
    "05_interpolation.moss": (
        '{"greeting":"hello, ada","summary":"you have 42 items",'
        '"status":"active is true"}\n'
    ),
    "06_lists.moss": (
        '{"type":"catalog","tags":["fast","simple","clear"],'
        '"numbers":[1,2,3,5,8]}\n'
    ),
    "07_plexi_poc.moss": (
        '{"protocol":"pgap/1","type":"ready","id":null,'
        '"payload":{"service":"moss-demo","version":"0.1.0",'
        '"ready_message":"moss-demo v0.1.0 is online"},"error":null}\n'
    ),
    "08_module_input.moss": '{"type":"greeting","message":"hello, ","doubled":null}\n',
    "09_pipeline_sink.moss": (
        '{"protocol":"pgap/1","type":"alert","payload":{"heading":"new  from ",'
        '"original_type":null,"score":null}}\n'
    ),
    "09_pipeline_source.moss": (
        '{"protocol":"pgap/1","type":"event",'
        '"payload":{"user":"ada","action":"login","score":42}}\n'
    ),
    "10_arithmetic.moss": (
        '13\n7\n42\n5.5\n14\n20\n"Hello, world!"\n3\n"square area: 49"\n'
    ),
    "11_conditionals.moss": (
        '"x is greater than y"\n'
        '"grade: C"\n'
        '"hello alice"\n'
        '"you are not bob"\n'
        '"a is true and b is false"\n'
        '"at least one is true"\n'
        '"normal temperature"\n'
        '"entry allowed"\n'
    ),
    "12_loops.moss": (
        '"Fruits:"\n"apple"\n"banana"\n"cherry"\n'
        '"Counting 1 to 5:"\n1\n2\n3\n4\n5\n'
        '"Skip 3:"\n1\n2\n4\n5\n'
        '"Stop at 4:"\n1\n2\n3\n'
        '"Greater than 3:"\n4\n5\n6\n'
    ),
    "13_functions.moss": (
        '"Hello, Alice!"\n'
        '"Hello, Bob! (LOUD)"\n'
        '7\n10\n11\n"first"\n"third"\n3\n100\n4\n6\n'
    ),
    "TEACHING.moss": (
        '"a simple piece of text"\n'
        '42\n'
        'true\n'
        '["apple","banana","cherry"]\n'
        '{"name":"ada","age":36,"is_admin":true}\n'
        '{"type":"example","message":"hi, hello! you have 10 items.",'
        '"details":{"status":"ok","count":10}}\n'
    ),
}


class ExampleGoldenTests(unittest.TestCase):
    def run_moss(self, path):
        return subprocess.run(
            [str(MOSS), "run", str(path)],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

    def test_every_example_has_golden_output(self):
        example_names = {path.name for path in (ROOT / "examples").glob("*.moss")}

        self.assertEqual(example_names, set(EXAMPLE_OUTPUTS))

    def test_examples_match_golden_output(self):
        for name, expected in EXAMPLE_OUTPUTS.items():
            with self.subTest(example=name):
                result = self.run_moss(ROOT / "examples" / name)

                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout, expected)


if __name__ == "__main__":
    unittest.main()
