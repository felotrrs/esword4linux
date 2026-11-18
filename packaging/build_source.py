#!/usr/bin/env python3
"""Build the Debian 3.0 (quilt) source package for esword4linux.

The upstream ``.orig.tar.xz`` is generated here because ``dpkg-source`` never
creates it for the ``3.0 (quilt)`` format. The archive contains the tracked
source tree plus the pinned wheelhouse under ``.build/wheelhouse`` so that a
Launchpad buildd can assemble the private runtime without PyPI access.

The wheelhouse never enters Git: it is read from the local, Git-ignored
``.build/wheelhouse`` directory and validated against the SHA-256 hashes in
``packaging/runtime-requirements.txt`` with
``packaging/stage_runtime.py:verify_wheelhouse``.

Usage:
  packaging/build_source.py                  # requires a clean Git tree
  packaging/build_source.py --allow-dirty    # validate local changes
  packaging/build_source.py --verify-build   # also rebuild the .deb offline

Generated artifacts are copied to ``dist/src``. Nothing is signed, uploaded or
published unless ``--sign-key`` is passed explicitly; signing only signs the
``.dsc`` and ``_source.changes`` for a later, manual upload.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_WHEELHOUSE = REPO_ROOT / ".build" / "wheelhouse"
DEFAULT_OUTPUT = REPO_ROOT / "dist" / "src"
DEFAULT_REQUIREMENTS = REPO_ROOT / "packaging" / "runtime-requirements.txt"

# e-Sword modules are never distributable as part of the source package.
MODULE_SUFFIXES = (
    ".bbl", ".bbli", ".bblx",
    ".cmt", ".cmti", ".cmtx",
    ".dct", ".dcti", ".dctx",
    ".lex", ".lexi", ".lexx",
    ".top", ".topi", ".topx",
    ".dev", ".devx",
    ".ref", ".refi", ".refx",
    ".har", ".harx",
    ".map", ".mapx",
    ".twm", ".lanx", ".ocx",
)

PUBLICATION_MARKER = "NOT-PUBLICATION-READY.txt"

sys.path.insert(0, str(REPO_ROOT / "packaging"))
import stage_runtime  # noqa: E402  (reuse the pinned-wheel validation)


class BuildError(Exception):
    """A validation or build step failed."""


def fail(message: str) -> "NoReturn":
    raise BuildError(message)


def run(cmd: list[str], *, cwd: Path | None = None,
        env: dict[str, str] | None = None, capture: bool = False) -> str:
    printable = " ".join(cmd)
    if capture:
        result = subprocess.run(cmd, cwd=cwd, env=env, text=True,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE)
        if result.returncode != 0:
            fail(f"command failed ({result.returncode}): {printable}\n"
                 f"{result.stderr.strip()}")
        return result.stdout
    result = subprocess.run(cmd, cwd=cwd, env=env)
    if result.returncode != 0:
        fail(f"command failed ({result.returncode}): {printable}")
    return ""


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_changelog() -> dict[str, str]:
    fields = {}
    for key in ("Source", "Version", "Distribution", "Date"):
        fields[key] = run(
            ["dpkg-parsechangelog", "-l", "debian/changelog", "-S", key],
            cwd=REPO_ROOT, capture=True,
        ).strip()
    if not all(fields.values()):
        fail("could not read Source/Version/Distribution/Date from the changelog")
    return fields


def epoch_from_date(date: str) -> int:
    return int(run(["date", "-u", "-d", date, "+%s"], capture=True).strip())


def git_files() -> list[tuple[str, str]]:
    raw = run(["git", "ls-files", "-s", "-z"], cwd=REPO_ROOT, capture=True)
    files: list[tuple[str, str]] = []
    for record in raw.split("\0"):
        if not record:
            continue
        meta, path = record.split("\t", 1)
        mode = meta.split(" ", 1)[0]
        files.append((mode, path))
    return files


def untracked_files() -> list[str]:
    raw = run(["git", "ls-files", "--others", "--exclude-standard", "-z"],
              cwd=REPO_ROOT, capture=True)
    return [path for path in raw.split("\0") if path]


def require_clean_tree(allow_dirty: bool) -> None:
    status = run(["git", "status", "--porcelain", "-uno"], cwd=REPO_ROOT,
                 capture=True)
    if status.strip() and not allow_dirty:
        fail("the Git working tree has uncommitted tracked changes:\n"
             f"{status.rstrip()}\n"
             "Commit them, or rerun with --allow-dirty for a validation-only "
             "package (not suitable for publication).")


def check_tracked_content(files: list[tuple[str, str]]) -> None:
    for _mode, path in files:
        name = path.rsplit("/", 1)[-1]
        if path.endswith(".whl"):
            fail(f"a wheel is tracked in Git: {path}")
        if name.endswith(MODULE_SUFFIXES):
            fail(f"an e-Sword module is tracked in Git: {path}")
        if path.startswith(".build/"):
            fail(f"build output is tracked in Git: {path}")


def stage_tree(root: Path, files: list[tuple[str, str]], allow_dirty: bool) -> None:
    for mode, rel in files:
        src = REPO_ROOT / rel
        dst = root / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        if mode == "120000":
            if not src.is_symlink():
                fail(f"tracked symlink is missing: {rel}")
            os.symlink(os.readlink(src), dst)
        elif mode in ("100644", "100755"):
            if not src.is_file():
                fail(f"tracked file is missing from the working tree: {rel}")
            shutil.copyfile(src, dst)
            os.chmod(dst, 0o755 if mode == "100755" else 0o644)
        elif mode == "160000":
            fail(f"submodules are not supported in the source package: {rel}")
        else:
            fail(f"unsupported Git mode {mode} for {rel}")

    for current, dirs, _files in os.walk(root):
        os.chmod(current, 0o755)
        for name in dirs:
            path = Path(current) / name
            if not path.is_symlink():
                os.chmod(path, 0o755)

    if not allow_dirty:
        return

    # List the tracked paths that differ from HEAD when validating dirty work.
    diff = run(["git", "diff", "--name-only", "HEAD"], cwd=REPO_ROOT,
               capture=True).strip()
    if diff:
        print("build_source: including uncommitted changes:")
        for path in diff.splitlines():
            print(f"  {path}")


def stage_wheelhouse(root: Path, wheels: dict[str, Path], epoch: int) -> None:
    target = root / ".build" / "wheelhouse"
    target.mkdir(parents=True, exist_ok=True)
    for path in wheels.values():
        dst = target / path.name
        shutil.copyfile(path, dst)
        os.chmod(dst, 0o644)
        os.utime(dst, (epoch, epoch))


def build_orig(work: Path, root_name: str, epoch: int, dest: Path) -> None:
    env = {key: value for key, value in os.environ.items()
           if key not in {"TAR_OPTIONS", "XZ_OPT", "XZ_DEFAULTS"}}
    tar_cmd = [
        "tar", "-C", str(work),
        "--sort=name", "--format=gnu",
        "--owner=0", "--group=0", "--numeric-owner",
        f"--mtime=@{epoch}",
        f"--exclude={root_name}/debian",
        "-cf", "-", root_name,
    ]
    xz_cmd = ["xz", "-6", "-T1", "-c"]
    with dest.open("wb") as handle:
        producer = subprocess.Popen(tar_cmd, stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE, env=env)
        compressor = subprocess.Popen(xz_cmd, stdin=producer.stdout,
                                      stdout=handle, stderr=subprocess.PIPE,
                                      env=env)
        assert producer.stdout is not None
        producer.stdout.close()
        _, xz_err = compressor.communicate()
        tar_err = producer.stderr.read() if producer.stderr else b""
        producer.wait()
        if producer.returncode != 0:
            fail(f"tar failed: {tar_err.decode(errors='replace').strip()}")
        if compressor.returncode != 0:
            fail(f"xz failed: {xz_err.decode(errors='replace').strip()}")


def orig_members(orig: Path) -> list[str]:
    with tarfile.open(orig, "r:xz") as archive:
        return archive.getnames()


def validate_orig(orig: Path, root_name: str, wheels: dict[str, Path],
                  epoch: int, tracked: list[tuple[str, str]]) -> None:
    if not orig.is_file():
        fail(f"orig tarball not found: {orig}")
    members = orig_members(orig)
    prefix = f"{root_name}/"
    for member in members:
        if not member.startswith(prefix) and member != root_name:
            fail(f"orig member outside {prefix!r}: {member}")
        if member.startswith(f"{prefix}debian/") or member == f"{prefix}debian":
            fail("the orig tarball must not contain debian/")
        if member.startswith(f"{prefix}.build/"):
            allowed = {
                f"{prefix}.build",
                f"{prefix}.build/",
                f"{prefix}.build/wheelhouse",
                f"{prefix}.build/wheelhouse/",
            }
            if member not in allowed and not re.fullmatch(
                    re.escape(prefix) + r"\.build/wheelhouse/[^/]+\.whl",
                    member):
                fail(f"unexpected .build content in the orig: {member}")

    expected = {f"{prefix}.build/wheelhouse/{path.name}": path
                for path in wheels.values()}
    found = {member for member in members
             if re.fullmatch(re.escape(prefix) + r"\.build/wheelhouse/[^/]+\.whl",
                             member)}
    if found != set(expected):
        missing = sorted(set(expected) - found)
        extra = sorted(found - set(expected))
        fail(f"wheelhouse mismatch in the orig; missing={missing} extra={extra}")

    with tempfile.TemporaryDirectory(prefix="esword4linux-orig-check-") as tmp:
        for member, source in expected.items():
            with tarfile.open(orig, "r:xz") as archive:
                extracted = archive.extractfile(member)
                if extracted is None:
                    fail(f"could not read {member} from the orig")
                staged = Path(tmp) / source.name
                with staged.open("wb") as handle:
                    shutil.copyfileobj(extracted, handle)
            if sha256(staged) != sha256(source):
                fail(f"wheel hash changed inside the orig: {source.name}")

    # The archive must be reproducible: every member shares the changelog date.
    with tarfile.open(orig, "r:xz") as archive:
        for info in archive.getmembers():
            if info.mtime != epoch:
                fail(f"non-deterministic mtime for {info.name}: {info.mtime}")
        archived = {info.name for info in archive.getmembers()
                    if info.isfile() or info.issym()}

    expected_files = {f"{prefix}{rel}" for _mode, rel in tracked
                      if not rel.startswith("debian/")}
    expected_files |= set(expected)
    if archived != expected_files:
        missing = sorted(expected_files - archived)
        extra = sorted(archived - expected_files)
        fail(f"orig file set mismatch; missing={missing} extra={extra}")


def validate_debian_tar(path: Path) -> None:
    members = orig_members(path)
    if not members:
        fail("the Debian tar archive is empty")
    for member in members:
        normalized = member[2:] if member.startswith("./") else member
        if normalized and not (normalized == "debian"
                               or normalized.startswith("debian/")):
            fail(f"unexpected member in the Debian tar: {member}")
    if any(member.endswith(".whl") for member in members):
        fail("wheels must not be stored in the Debian diff")


def deb822_text(path: Path) -> str:
    """Return the deb822 payload, stripping an optional OpenPGP clearsign."""
    text = path.read_text(encoding="utf-8")
    if not text.startswith("-----BEGIN PGP SIGNED MESSAGE-----"):
        return text
    lines = text.splitlines()
    start = 0
    for index, line in enumerate(lines):
        if not line.strip():
            start = index + 1
            break
    payload = []
    for line in lines[start:]:
        if line.startswith("-----BEGIN PGP SIGNATURE-----"):
            break
        payload.append(line[2:] if line.startswith("- ") else line)
    return "\n".join(payload)


def parse_deb822(path: Path) -> dict[str, str]:
    fields: dict[str, str] = {}
    key = None
    for line in deb822_text(path).splitlines():
        if not line.strip():
            continue
        if line[0] in " \t":
            if key is None:
                fail(f"malformed continuation line in {path.name}")
            value = line.strip()
            fields[key] = f"{fields[key]}\n{value}" if fields[key] else value
            continue
        if ":" not in line:
            fail(f"malformed field in {path.name}: {line!r}")
        key, value = line.split(":", 1)
        fields[key] = value.strip()
    return fields


def check_checksums(path: Path, fields: dict[str, str], directory: Path,
                    section: str, with_metadata: bool = False) -> None:
    if section not in fields:
        fail(f"{path.name} has no {section} field")
    entries = fields[section].splitlines()
    if not entries:
        fail(f"{path.name} has an empty {section} field")
    for line in entries:
        parts = line.split()
        if section == "Files":
            expected = 5 if with_metadata else 3
            if len(parts) != expected:
                fail(f"malformed Files entry in {path.name}: {line!r}")
            digest, size, name = parts[0], parts[1], parts[-1]
        else:
            if len(parts) != 3:
                fail(f"malformed {section} entry in {path.name}: {line!r}")
            digest, size, name = parts
        target = directory / name
        if not target.is_file():
            fail(f"{path.name} references a missing file: {name}")
        if str(target.stat().st_size) != size:
            fail(f"size mismatch for {name} in {path.name}")
        if section == "Files":
            actual = hashlib.md5(target.read_bytes()).hexdigest()
        elif section == "Checksums-Sha1":
            actual = hashlib.sha1(target.read_bytes()).hexdigest()
        else:
            actual = sha256(target)
        if actual != digest:
            fail(f"checksum mismatch for {name} in {path.name}")


def validate_source_package(dsc: Path, changes: Path, source: str,
                            version: str, upstream: str,
                            distribution: str) -> None:
    fields = parse_deb822(dsc)
    if fields.get("Format") != "3.0 (quilt)":
        fail(f"unexpected source format: {fields.get('Format')!r}")
    if fields.get("Source") != source:
        fail(f"unexpected source name: {fields.get('Source')!r}")
    if fields.get("Version") != version:
        fail(f"unexpected source version: {fields.get('Version')!r}")
    for section in ("Checksums-Sha1", "Checksums-Sha256", "Files"):
        check_checksums(dsc, fields, dsc.parent, section)

    change = parse_deb822(changes)
    if change.get("Source") != source:
        fail(f"unexpected Source in {changes.name}: {change.get('Source')!r}")
    if change.get("Version") != version:
        fail(f"unexpected Version in {changes.name}: {change.get('Version')!r}")
    if change.get("Architecture") != "source":
        fail(f"unexpected Architecture in {changes.name}")
    if change.get("Distribution") != distribution:
        fail(f"unexpected Distribution in {changes.name}: "
             f"{change.get('Distribution')!r}")
    files = change.get("Files", "")
    for required in (dsc.name, f"{source}_{upstream}.orig.tar.xz",
                     f"{source}_{version}.debian.tar.xz"):
        if required not in files:
            fail(f"{changes.name} does not include {required}")
    for section in ("Checksums-Sha1", "Checksums-Sha256"):
        check_checksums(changes, change, changes.parent, section)
    check_checksums(changes, change, changes.parent, "Files",
                    with_metadata=True)


def find_artifacts(work: Path, source: str, version: str,
                   upstream: str) -> dict[str, Path]:
    names = {
        "orig": f"{source}_{upstream}.orig.tar.xz",
        "debian": f"{source}_{version}.debian.tar.xz",
        "dsc": f"{source}_{version}.dsc",
        "changes": f"{source}_{version}_source.changes",
        "buildinfo": f"{source}_{version}_source.buildinfo",
    }
    artifacts = {}
    for key, name in names.items():
        path = work / name
        if not path.is_file():
            fail(f"expected artifact was not generated: {name}")
        artifacts[key] = path
    return artifacts


def unpack_source(dsc: Path, parent: Path) -> Path:
    if parent.exists():
        shutil.rmtree(parent)
    # dpkg-source unpacks directly into the requested directory.
    run(["dpkg-source", "-x", str(dsc), str(parent)])
    if not (parent / ".build" / "wheelhouse").is_dir():
        fail(f"dpkg-source -x did not produce the expected tree in {parent}")
    return parent


def verify_binary_build(root: Path) -> Path:
    if shutil.which("unshare") is None:
        fail("--verify-build needs util-linux (unshare) for offline isolation")
    try:
        run(["unshare", "-rn", "true"])
    except BuildError as exc:
        fail("cannot create a network-isolated namespace for --verify-build "
             f"({exc})")
    run(["unshare", "-rn", "dpkg-buildpackage", "-b", "-us", "-uc"], cwd=root)
    debs = sorted(root.parent.glob("*.deb"))
    if not debs:
        fail("the offline rebuild did not produce a .deb")
    return max(debs, key=lambda path: path.stat().st_size)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build the esword4linux Debian source package.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--allow-dirty", action="store_true",
                        help="include uncommitted tracked changes; the result "
                             "is not suitable for publication")
    parser.add_argument("--sign-key", metavar="KEYID",
                        help="sign the .dsc and _source.changes with KEYID "
                             "(never done by default)")
    parser.add_argument("--verify-build", action="store_true",
                        help="also rebuild the .deb from the .dsc inside an "
                             "offline network namespace")
    parser.add_argument("--keep-workdir", action="store_true",
                        help="keep the staging directory for inspection")
    parser.add_argument("--wheelhouse", type=Path, default=DEFAULT_WHEELHOUSE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--requirements", type=Path,
                        default=DEFAULT_REQUIREMENTS)
    args = parser.parse_args(argv)

    for tool in ("git", "tar", "xz", "dpkg-parsechangelog",
                 "dpkg-buildpackage", "dpkg-source"):
        if shutil.which(tool) is None:
            fail(f"required tool not found: {tool}")

    fields = parse_changelog()
    source = fields["Source"]
    version = fields["Version"]
    upstream = version.rsplit("-", 1)[0] if "-" in version else version
    distribution = fields["Distribution"]
    root_name = f"{source}-{upstream}"
    epoch = epoch_from_date(fields["Date"])

    if distribution in {"unstable", "experimental"}:
        fail(f"distribution {distribution!r} cannot be uploaded to a Launchpad "
             "PPA; use an Ubuntu series such as 'noble' in debian/changelog")

    require_clean_tree(args.allow_dirty)

    if args.allow_dirty:
        pending = untracked_files()
        if pending:
            print("build_source: warning: these untracked files are not part "
                  "of the source package (commit them to include them):")
            for path in pending:
                print(f"  {path}")

    files = git_files()
    check_tracked_content(files)

    app_version = stage_runtime.app_version(REPO_ROOT / "src" / "esword4linux")
    if app_version != upstream:
        fail(f"application version {app_version!r} does not match the Debian "
             f"upstream version {upstream!r}")

    try:
        wheels = stage_runtime.verify_wheelhouse(args.wheelhouse,
                                                 args.requirements)
    except SystemExit as exc:
        fail(f"wheelhouse validation failed (exit {exc.code})")

    print(f"build_source: {source} {version} ({distribution})")
    print(f"  upstream version: {upstream}")
    print(f"  wheelhouse: {args.wheelhouse}")
    for name, path in sorted(wheels.items()):
        print(f"    {name}: {path.name} ({path.stat().st_size} bytes)")

    build_dir = REPO_ROOT / ".build"
    build_dir.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="esword4linux-source-",
                                 dir=str(build_dir)))
    try:
        root = work / root_name
        stage_tree(root, files, args.allow_dirty)
        stage_wheelhouse(root, wheels, epoch)

        orig = work / f"{source}_{upstream}.orig.tar.xz"
        build_orig(work, root_name, epoch, orig)
        validate_orig(orig, root_name, wheels, epoch, files)
        print(f"  orig: {orig.name} ({orig.stat().st_size} bytes)")

        cmd = ["dpkg-buildpackage", "-S", "-sa", "-d"]
        if args.sign_key:
            cmd.append(f"-k{args.sign_key}")
        else:
            cmd.extend(["-us", "-uc"])
        run(cmd, cwd=root,
            env={**os.environ, "SOURCE_DATE_EPOCH": str(epoch)})

        artifacts = find_artifacts(work, source, version, upstream)
        validate_orig(artifacts["orig"], root_name, wheels, epoch, files)
        validate_debian_tar(artifacts["debian"])
        validate_source_package(artifacts["dsc"], artifacts["changes"],
                                source, version, upstream, distribution)

        # dpkg-source -x verifies the .dsc checksums and the archive layout.
        unpacked = unpack_source(artifacts["dsc"], work / "unpacked")
        unpacked_wheels = unpacked / ".build" / "wheelhouse"
        for name, path in wheels.items():
            target = unpacked_wheels / path.name
            if not target.is_file() or sha256(target) != sha256(path):
                fail(f"unpacked wheel mismatch: {name}")
        shutil.rmtree(unpacked)

        for name in wheels:
            path = root / ".build" / "wheelhouse" / wheels[name].name
            if not path.is_file() or sha256(path) != sha256(wheels[name]):
                fail("debian/rules clean removed or modified the wheelhouse")

        if args.verify_build:
            verify_root = unpack_source(artifacts["dsc"], work / "verify")
            try:
                deb = verify_binary_build(verify_root)
            except BuildError as exc:
                if args.allow_dirty:
                    fail(f"{exc}\nThe offline rebuild used the dirty working "
                         "tree; uncommitted runtime assets (for example the "
                         "application icon pair) can make validate_runtime.py "
                         "fail. Commit them or validate from a clean tree.")
                raise
            print(f"  offline rebuild: {deb.name} ({deb.stat().st_size} bytes)")

        args.output.mkdir(parents=True, exist_ok=True)
        marker = args.output / PUBLICATION_MARKER
        if marker.exists():
            marker.unlink()
        for key, path in artifacts.items():
            if key == "orig":
                continue
            shutil.copyfile(path, args.output / path.name)
            print(f"  wrote {args.output / path.name}")
        shutil.copyfile(artifacts["orig"], args.output / artifacts["orig"].name)
        print(f"  wrote {args.output / artifacts['orig'].name}")

        if args.allow_dirty:
            marker.write_text(
                "This source package was generated with --allow-dirty and "
                "includes uncommitted changes.\n"
                "It is NOT suitable for publication. Commit the changes and "
                "rerun without --allow-dirty.\n",
                encoding="utf-8",
            )
            print("\nWARNING: --allow-dirty was used. The package in "
                  f"{args.output} is NOT publication-ready.")
        if not args.sign_key:
            print("Note: the .dsc and _source.changes are unsigned. Signing is "
                  "required before a PPA upload and is never automatic.")
    finally:
        if args.keep_workdir:
            print(f"  workdir kept: {work}")
        else:
            shutil.rmtree(work, ignore_errors=True)

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except BuildError as exc:
        print(f"build_source: error: {exc}", file=sys.stderr)
        raise SystemExit(1)
