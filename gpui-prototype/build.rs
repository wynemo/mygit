use std::process::Command;

fn main() {
    println!("cargo:rerun-if-changed=build.rs");
    println!("cargo:rerun-if-changed=assets/windows/mygit.rc");
    println!("cargo:rerun-if-changed=assets/icons/mygit.ico");
    if std::env::var("CARGO_CFG_TARGET_OS").as_deref() == Ok("windows") {
        embed_resource::compile_for(
            "assets/windows/mygit.rc",
            ["mygit-gpui"],
            embed_resource::NONE,
        )
        .manifest_required()
        .expect("Unable to embed the Windows application icon");
    }
    let output = Command::new("git")
        .args(["rev-parse", "--short=8", "HEAD"])
        .output();
    let commit = output
        .ok()
        .filter(|o| o.status.success())
        .and_then(|o| String::from_utf8(o.stdout).ok())
        .map(|s| s.trim().to_owned())
        .filter(|s| !s.is_empty())
        .unwrap_or_else(|| "—".into());
    println!("cargo:rustc-env=MYGIT_BUILD_COMMIT={commit}");
    // Track HEAD and its symbolic ref, including worktree Git directories.
    for reference in ["HEAD", "HEAD^{commit}"] {
        let args = if reference == "HEAD" {
            vec!["rev-parse", "--git-path", "HEAD"]
        } else {
            vec!["symbolic-ref", "-q", "HEAD"]
        };
        if let Ok(output) = Command::new("git").args(args).output() {
            if output.status.success() {
                let value = String::from_utf8_lossy(&output.stdout);
                let path = if reference == "HEAD" {
                    value.trim().to_owned()
                } else {
                    Command::new("git")
                        .args(["rev-parse", "--git-path", value.trim()])
                        .output()
                        .ok()
                        .filter(|o| o.status.success())
                        .map(|o| String::from_utf8_lossy(&o.stdout).trim().to_owned())
                        .unwrap_or_default()
                };
                if !path.is_empty() {
                    println!("cargo:rerun-if-changed={path}");
                }
            }
        }
    }
}
