import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).with_name("grep_lite.py")


def test_single_file(tmp_path):
    path = tmp_path / "fruit.txt"
    path.write_text("apple\nbanana\npineapple\n")
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "apple", str(path)], capture_output=True, text=True
    )
    assert result.stdout == "apple\npineapple\n"
    assert result.returncode == 0
