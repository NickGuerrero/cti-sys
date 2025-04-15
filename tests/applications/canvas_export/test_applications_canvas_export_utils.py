import csv
import os
import textwrap
from src.applications.canvas_export.utils import get_csv_as_stream, get_csv_as_tmp_file

class TestCanvasExportUtils:
    def test_get_csv_as_tmp_file_creates_valid_csv(self):
        headers = ["First Name", "Age"]
        rows = [["Alice", "25"], ["Bob", "26"]]
        filename = "created_test_file"

        file_path = get_csv_as_tmp_file(
            headers=headers,
            rows=rows,
            filename=filename
        )

        assert os.path.exists(file_path)
        assert file_path.endswith(".csv")
        assert os.path.basename(file_path).startswith(f"{filename}_")

        # file content should match
        with open(file_path, newline="") as f:
            reader = list(csv.reader(f))
            assert reader == [headers] + rows

        # clean up
        os.remove(file_path)
    
    def test_get_csv_as_stream_returns_valid_data(self):
        headers = ["First Name", "Age"]
        rows = [["Alice", "25"], ["Bob", "26"]]

        csv_stream = get_csv_as_stream(
            headers=headers,
            rows=rows,
        )

        expected = textwrap.dedent("""\
            First Name,Age
            Alice,25
            Bob,26
        """).strip()

        # normalize line endings and trim
        assert csv_stream.replace("\r\n", "\n").strip() == expected.strip()
