"""Build the Windows portable distribution using the active CPython installation."""
from pathlib import Path
import hashlib
import json
import shutil
import sys
from zipfile import ZipFile, ZIP_DEFLATED

root = Path(__file__).resolve().parent
output = root / "dist"
package = output / "morning-jog-1.5.5-windows-x64"
if package.exists():
    raise FileExistsError(package)
package.mkdir(parents=True)
for source in root.iterdir():
    if source.is_file() and source.suffix in (".py", ".md", ".txt", ".cmd"):
        shutil.copyfile(source, package / source.name)
for folder in ("morning", "docs", "licenses", "assets"):
    shutil.copytree(root / folder, package / folder)
runtime = package / "runtime"
runtime.mkdir()
prefix = Path(sys.base_prefix)
for source in prefix.iterdir():
    if source.is_file() and (source.suffix.lower() in (".exe", ".dll", ".txt") or source.name == "LICENSE.txt"):
        shutil.copyfile(source, runtime / source.name)
for folder in ("Lib", "DLLs", "tcl"):
    shutil.copytree(prefix / folder, runtime / folder,
                    ignore=shutil.ignore_patterns("__pycache__", "site-packages", "test", "tests", "idlelib", "ensurepip"))
required = [runtime / "python.exe", runtime / "pythonw.exe", runtime / "tcl"]
if not all(path.exists() for path in required):
    raise RuntimeError("The Python installation must include the Tcl/Tk runtime.")
archive = output / (package.name + ".zip")
with ZipFile(archive, "w", ZIP_DEFLATED, compresslevel=3) as zip_file:
    for path in package.rglob("*"):
        if path.is_file():
            zip_file.write(path, path.relative_to(package))
with ZipFile(archive) as zip_file:
    if zip_file.testzip() is not None:
        raise RuntimeError("Archive verification failed.")
digest = hashlib.sha256(archive.read_bytes()).hexdigest()
(output / "SHA256SUMS.txt").write_text(digest + "  " + archive.name + "\n", encoding="utf-8")
print(archive)
