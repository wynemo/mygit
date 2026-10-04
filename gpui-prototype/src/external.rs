//! Keep the caller's PATH preference, with standard macOS package locations as fallback.
#[cfg(target_os = "macos")]
use std::path::{Path, PathBuf};
use std::process::Command;

pub(crate) fn command(name: &str) -> Command {
    #[cfg(target_os = "macos")]
    {
        let path = std::env::var_os("PATH");
        let directories: Vec<_> = path
            .as_deref()
            .map(std::env::split_paths)
            .into_iter()
            .flatten()
            .collect();
        let fallback =
            ["/opt/homebrew/bin", "/usr/local/bin", "/usr/bin", "/bin"].map(PathBuf::from);
        if let Some(program) = fallback_program(name, &directories, &fallback) {
            return Command::new(program);
        }
    }
    Command::new(name)
}

#[cfg(target_os = "macos")]
fn fallback_program(name: &str, path: &[PathBuf], fallback: &[PathBuf]) -> Option<PathBuf> {
    if !matches!(name, "git" | "rg" | "curl")
        || path
            .iter()
            .any(|directory| executable(&directory.join(name)))
    {
        return None;
    }
    fallback
        .iter()
        .map(|directory| directory.join(name))
        .find(|candidate| executable(candidate))
}

#[cfg(target_os = "macos")]
fn executable(path: &Path) -> bool {
    use std::os::unix::fs::PermissionsExt;
    path.metadata()
        .is_ok_and(|metadata| metadata.is_file() && metadata.permissions().mode() & 0o111 != 0)
}

#[cfg(all(test, target_os = "macos"))]
mod tests {
    use super::*;
    #[test]
    fn executable_check_rejects_directories_and_non_executable_files() {
        use std::os::unix::fs::PermissionsExt;
        let root =
            std::env::temp_dir().join(format!("mygit-executable-check-{}", std::process::id()));
        std::fs::create_dir_all(&root).unwrap();
        let path = root.join("tool");
        std::fs::write(&path, b"#!/bin/sh\nexit 0\n").unwrap();
        std::fs::set_permissions(&path, std::fs::Permissions::from_mode(0o600)).unwrap();
        assert!(!executable(&path));
        assert!(!executable(&root));
        std::fs::set_permissions(&path, std::fs::Permissions::from_mode(0o700)).unwrap();
        assert!(executable(&path));
        let preferred = root.join("preferred");
        let fallback = root.join("fallback");
        std::fs::create_dir_all(&preferred).unwrap();
        std::fs::create_dir_all(&fallback).unwrap();
        for directory in [&preferred, &fallback] {
            let tool = directory.join("rg");
            std::fs::write(&tool, b"#!/bin/sh\nprintf fixture-tool\n").unwrap();
            std::fs::set_permissions(&tool, std::fs::Permissions::from_mode(0o700)).unwrap();
        }
        // Explicit PATH tools keep normal subprocess lookup; fallback only handles absence.
        assert!(
            fallback_program(
                "rg",
                std::slice::from_ref(&preferred),
                std::slice::from_ref(&fallback)
            )
            .is_none()
        );
        let resolved = fallback_program("rg", &[], std::slice::from_ref(&fallback)).unwrap();
        let output = Command::new(resolved).output().unwrap();
        assert!(output.status.success());
        assert_eq!(output.stdout, b"fixture-tool");
        assert!(fallback_program("unrecognized", &[], std::slice::from_ref(&fallback)).is_none());
        std::fs::set_permissions(fallback.join("rg"), std::fs::Permissions::from_mode(0o600))
            .unwrap();
        assert!(fallback_program("rg", &[], std::slice::from_ref(&fallback)).is_none());
        std::fs::remove_dir_all(root).unwrap();
    }
}
