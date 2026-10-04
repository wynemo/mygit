#!/usr/bin/env python3
"""Build a self-contained macOS app; Python is only a build dependency."""
import argparse
import json
import pathlib
import plistlib
import shutil
import subprocess
import sys
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--output", type=pathlib.Path)
    args = parser.parse_args()
    root = pathlib.Path(__file__).resolve().parents[1]
    if sys.platform != "darwin":
        parser.error("macOS packaging must run on macOS")
    destination = (args.output or root / "dist" / "MyGit.app").resolve()
    if destination.exists():
        parser.error(f"output already exists: {destination}; choose a new output path")
    profile = "debug" if args.debug else "release"
    command = ["cargo", "build", "--locked", "--manifest-path", str(root / "Cargo.toml")]
    if not args.debug:
        command.append("--release")
    subprocess.run(command, check=True)
    metadata = json.loads(subprocess.check_output([
        "cargo", "metadata", "--no-deps", "--format-version", "1",
        "--manifest-path", str(root / "Cargo.toml"),
    ]))
    package = next(p for p in metadata["packages"] if p["name"] == "mygit-gpui")
    version = package["version"]
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="mygit-package-", dir=destination.parent) as temp:
        app = pathlib.Path(temp) / "MyGit.app"
        contents = app / "Contents"
        executable = contents / "MacOS" / "MyGit"
        executable.parent.mkdir(parents=True)
        resources = contents / "Resources"
        resources.mkdir()
        shutil.copy2(pathlib.Path(metadata["target_directory"]) / profile / "mygit-gpui", executable)
        shutil.copy2(root / "assets" / "icons" / "mygit.icns", resources / "mygit.icns")
        info = {
            "CFBundleExecutable": "MyGit", "CFBundleName": "MyGit",
            "CFBundleDisplayName": "MyGit", "CFBundleIdentifier": "local.mygit.gpui",
            "CFBundlePackageType": "APPL", "CFBundleIconFile": "mygit.icns",
            "CFBundleShortVersionString": version, "CFBundleVersion": version,
            "NSHighResolutionCapable": True,
            "NSHumanReadableCopyright": "MyGit contributors",
        }
        with (contents / "Info.plist").open("wb") as stream:
            plistlib.dump(info, stream)
        subprocess.run(["plutil", "-lint", str(contents / "Info.plist")], check=True)
        subprocess.run(["codesign", "--force", "--sign", "-", str(app)], check=True)
        subprocess.run(["codesign", "--verify", "--strict", str(app)], check=True)
        app.rename(destination)
    print(destination)


if __name__ == "__main__":
    main()
