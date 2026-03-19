"""Download transfer object from storage."""

import shutil
import sys
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import urlparse

import pygfried
import requests
from django.conf import settings

from a3m.bag import is_bag
from a3m.client import metrics
from a3m.executeOrRunSubProcess import executeOrRun

HTTP_SCHEMES = ("http", "https")
FILE_SCHEMES = "file"

EXTRACTABLE_PUIDS = (
    "fmt/411",
    "x-fmt/266",
    "x-fmt/266",
    "x-fmt/263",
    "fmt/484",
    "x-fmt/265",
)


class RetrievalError(Exception):
    pass


@contextmanager
def _create_tmpdir(suffix, purpose=None):
    prefix = f"a3m.{purpose}." if purpose else "a3m."
    with TemporaryDirectory(
        prefix=prefix, suffix=f".{suffix}", dir=settings.TEMP_DIRECTORY
    ) as tmp_dir:
        yield Path(tmp_dir)


def _archived(path):
    puid = pygfried.identify(str(path))
    return puid in EXTRACTABLE_PUIDS


def _extract(job, path, destination):
    command = [
        "unar",
        "-force-directory",
        "-output-directory",
        str(destination),
        str(path),
    ]
    exit_code, stdout, stderr = executeOrRun("command", command, capture_output=True)
    if exit_code > 0:
        raise RetrievalError("Extraction failed, unar quit with exit code {exit_code}")

    output_dir = next(destination.iterdir())

    # Strip leading container.
    if len(list(output_dir.glob("*"))) == 1:
        candidate = next(output_dir.iterdir())
        if candidate.is_dir():
            return candidate

    return output_dir


# Subdirectory under the transfer where content must live; the workflow
# (assign_file_uuids, characterize_file, etc.) expects paths under objects/.
OBJECTS_SUBDIR = "objects"


def _transfer_file(job, path, transfer_path, transfer_id, copy=False):
    """Create a transfer from a single file or directory.

    Content is placed under transfer_path/objects/ so that File records
    get currentlocation like %transferDirectory%objects/... as expected
    by the rest of the workflow.
    Extraction is attempted for archives; the file is used as-is if it failed.
    """
    objects_dir = Path(transfer_path) / OBJECTS_SUBDIR
    with _create_tmpdir(transfer_id, purpose="transfer") as tmp_dir:
        if _archived(path):
            src = _extract(job, path, tmp_dir)
        else:
            src = path

        objects_dir.mkdir(parents=True, mode=0o770)

        if not copy:
            if src.is_dir():
                for item in src.iterdir():
                    dest = objects_dir / item.name
                    if item.is_dir():
                        shutil.copytree(str(item), str(dest), symlinks=False)
                    else:
                        shutil.copy2(str(item), str(dest), follow_symlinks=False)
            else:
                shutil.move(str(src), str(objects_dir / src.name))
            return

        if src.is_dir():
            for item in src.iterdir():
                dest = objects_dir / item.name
                if item.is_dir():
                    shutil.copytree(str(item), str(dest), symlinks=False)
                else:
                    shutil.copy2(str(item), str(dest), follow_symlinks=False)
            return

        shutil.copy2(str(src), str(objects_dir / src.name), follow_symlinks=False)


def _process_http_url(job, url, transfer_path, transfer_id):
    with _create_tmpdir(transfer_id, purpose="download") as tmp_dir:
        download = tmp_dir / Path(url.path).name
        try:
            with requests.get(
                url.geturl(), allow_redirects=True, stream=True, timeout=100
            ) as resp:
                resp.raise_for_status()
                with download.open("wb") as f:
                    for chunk in resp.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
        except requests.RequestException as err:
            raise RetrievalError(f"Error downloading object: {err}")
        _transfer_file(job, download, transfer_path, transfer_id, copy=False)


def _process_file_url(job, path, transfer_path, transfer_id):
    if not path.exists():
        raise RetrievalError(
            "Path given does not point to an existing file or directory"
        )

    if path.is_symlink():
        raise RetrievalError("Symlinks are not supported")

    if path.is_dir():
        objects_dir = Path(transfer_path) / OBJECTS_SUBDIR
        objects_dir.mkdir(parents=True, mode=0o770)
        for item in path.iterdir():
            dest = objects_dir / item.name
            if item.is_dir():
                shutil.copytree(str(item), str(dest), symlinks=False)
            else:
                shutil.copy2(str(item), str(dest), follow_symlinks=False)
        return

    if not path.is_file():
        raise RetrievalError(f"Type of file not supported {path}")

    _transfer_file(job, path, transfer_path, transfer_id, copy=True)


def main(job, transfer_id, transfer_path, url):
    metrics.transfer_started()

    # A3M-TODO: review AM workflow, are we too different?
    # A3M-TODO: should we be producing preservation events?
    # A3M-TODO: mimic verify_and_restructure_transfer_bag.py if bag
    # A3M-TODO: do not move to failed/ if we don't made it that far
    # A3M-TODO: split download and extraction in multiple modules?
    # A3M-TODO: check disk usage with shutil.disk_usage

    parsed = urlparse(url)

    try:
        if parsed.scheme in HTTP_SCHEMES:
            _process_http_url(job, parsed, Path(transfer_path), transfer_id)
        elif parsed.scheme in FILE_SCHEMES:
            _process_file_url(job, Path(parsed.path), Path(transfer_path), transfer_id)
        else:
            job.pyprint(f"Unsupported URL scheme: {parsed.scheme}", file=sys.stderr)
            return 1
    except RetrievalError as err:
        job.pyprint(f"Error retrievent contents: {err}", file=sys.stderr)
        return 1

    if is_bag(Path(transfer_path) / OBJECTS_SUBDIR):
        job.pyprint("Bags not supported yet!", file=sys.stderr)
        return 1


def call(jobs):
    job = jobs[0]
    with job.JobContext():
        transfer_id = job.args[1]
        transfer_path = job.args[2]
        url = job.args[3]
        job.set_status(main(job, transfer_id, transfer_path, url))
