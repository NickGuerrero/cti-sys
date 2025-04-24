import csv
import io
import os
import tempfile
from typing import Any, List

from dotenv import load_dotenv

def get_csv_as_stream(
    headers: List[str],
    rows: List[Any]
) -> str:
    """
    Use in-memory buffer to get CSV as string data. Returns the buffered string.
    """
    output_stream = io.StringIO()
    csv_writer = csv.writer(output_stream)

    csv_writer.writerow(headers)
    csv_writer.writerows(rows)

    output_stream.seek(0)

    return output_stream.getvalue()

def get_csv_as_tmp_file(
    headers: List[str],
    rows: List[Any],
    filename: str
) -> str:
    """
    Convert header and row data to a named file. Returns the path to the file.

    Uses the tempfile module to save the CSV file in the system's tmp directory.
    This saves the filename in the format of `"<prefix>_<random string>.<suffix>"`
    for uniqueness of files stored. All column data is written as str.
    """
    with tempfile.NamedTemporaryFile(mode="w", prefix=f"{filename}_", suffix=".csv", delete=False) as csvfile:
        csv_writer = csv.writer(csvfile)

        csv_writer.writerow(headers)
        csv_writer.writerows(rows)

    return csvfile.name

def get_canvas_access_token():
    load_dotenv(override=True)

    access_token = os.environ.get("CTI_ACCESS_TOKEN")
    if access_token is None:
        raise Exception("Access token not found")
    
    return access_token
