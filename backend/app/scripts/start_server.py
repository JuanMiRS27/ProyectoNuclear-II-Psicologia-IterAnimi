"""Arranque de Render: migra la base y reemplaza el proceso por Uvicorn."""

import os
import subprocess
import sys


def main() -> None:
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], check=True)
    os.execvp(
        sys.executable,
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", os.environ.get("PORT", "8000")],
    )


if __name__ == "__main__":
    main()
