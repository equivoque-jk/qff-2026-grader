from html.parser import HTMLParser
import os
from pathlib import Path
import sys
import tempfile
from types import ModuleType
import unittest
from unittest.mock import Mock, patch
import zipfile

from qff_grader.notebook import _offer_download


class LinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.text = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self.links.append(dict(attrs))

    def handle_data(self, data):
        self.text.append(data)


class NotebookDownloadTests(unittest.TestCase):
    def test_notebook_link_requests_download_and_preserves_escaped_path(self):
        previous = Path.cwd()
        with tempfile.TemporaryDirectory() as directory:
            os.chdir(directory)
            try:
                for name in ("QFF_attempt.zip", "제출 & '팀' <1>.zip"):
                    with self.subTest(name=name):
                        archive = Path("submissions") / name
                        archive.parent.mkdir(exist_ok=True)
                        with zipfile.ZipFile(archive, "w") as output:
                            output.writestr("submission.json", "{}")
                        with patch.dict(sys.modules, {"google.colab": None}), patch("IPython.get_ipython", return_value=object()), patch("IPython.display.display") as display:
                            self.assertEqual(_offer_download(archive.resolve()), "file_link")
                        display.assert_called_once()
                        link = display.call_args.args[0]
                        parser = LinkParser()
                        parser.feed(link._repr_html_())
                        self.assertEqual(len(parser.links), 1)
                        self.assertEqual(parser.links[0]["href"], str(archive))
                        self.assertIn("download", parser.links[0])
                        self.assertEqual(set(parser.links[0]), {"href", "download"})
                        self.assertIn(str(archive), "".join(parser.text))
            finally:
                os.chdir(previous)

    def test_colab_still_calls_native_download(self):
        colab = ModuleType("google.colab")
        colab.files = Mock()
        archive = Path("QFF_attempt.zip")
        with patch.dict(sys.modules, {"google.colab": colab}), patch("IPython.display.display") as display:
            self.assertEqual(_offer_download(archive), "colab_download")
        colab.files.download.assert_called_once_with(str(archive))
        display.assert_not_called()

    def test_plain_python_keeps_local_path_behavior(self):
        with patch.dict(sys.modules, {"google.colab": None}), patch("IPython.get_ipython", return_value=None), patch("IPython.display.display") as display:
            self.assertEqual(_offer_download(Path("QFF_attempt.zip")), "local_path")
        display.assert_not_called()


if __name__ == "__main__":
    unittest.main()
