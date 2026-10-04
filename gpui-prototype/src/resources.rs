//! Embedded icon resources: independent of the current directory and Python checkout.
use std::path::Path;

pub const ICONS: &[(&str, &[u8])] = &[
    (
        "icons/arrow_down.svg",
        include_bytes!("../assets/icons/arrow_down.svg"),
    ),
    (
        "icons/changes.svg",
        include_bytes!("../assets/icons/changes.svg"),
    ),
    (
        "icons/chevron-down.svg",
        include_bytes!("../assets/icons/chevron-down.svg"),
    ),
    (
        "icons/commit_icon.svg",
        include_bytes!("../assets/icons/commit_icon.svg"),
    ),
    ("icons/down.svg", include_bytes!("../assets/icons/down.svg")),
    (
        "icons/fetch.svg",
        include_bytes!("../assets/icons/fetch.svg"),
    ),
    (
        "icons/folder.svg",
        include_bytes!("../assets/icons/folder.svg"),
    ),
    (
        "icons/git_branch.svg",
        include_bytes!("../assets/icons/git_branch.svg"),
    ),
    (
        "icons/globe.svg",
        include_bytes!("../assets/icons/globe.svg"),
    ),
    (
        "icons/hourglass.svg",
        include_bytes!("../assets/icons/hourglass.svg"),
    ),
    (
        "icons/languages/file.svg",
        include_bytes!("../assets/icons/languages/file.svg"),
    ),
    (
        "icons/languages/golang.svg",
        include_bytes!("../assets/icons/languages/golang.svg"),
    ),
    (
        "icons/languages/javascript.svg",
        include_bytes!("../assets/icons/languages/javascript.svg"),
    ),
    (
        "icons/languages/markdown.svg",
        include_bytes!("../assets/icons/languages/markdown.svg"),
    ),
    (
        "icons/languages/python.svg",
        include_bytes!("../assets/icons/languages/python.svg"),
    ),
    (
        "icons/languages/rust.svg",
        include_bytes!("../assets/icons/languages/rust.svg"),
    ),
    (
        "icons/languages/typescript.svg",
        include_bytes!("../assets/icons/languages/typescript.svg"),
    ),
    (
        "icons/project.svg",
        include_bytes!("../assets/icons/project.svg"),
    ),
    ("icons/pull.svg", include_bytes!("../assets/icons/pull.svg")),
    ("icons/push.svg", include_bytes!("../assets/icons/push.svg")),
    (
        "icons/refresh.svg",
        include_bytes!("../assets/icons/refresh.svg"),
    ),
    (
        "icons/search.svg",
        include_bytes!("../assets/icons/search.svg"),
    ),
    (
        "icons/settings.svg",
        include_bytes!("../assets/icons/settings.svg"),
    ),
    ("icons/star.svg", include_bytes!("../assets/icons/star.svg")),
    ("icons/up.svg", include_bytes!("../assets/icons/up.svg")),
];

pub fn load(path: &str) -> Option<&'static [u8]> {
    ICONS
        .iter()
        .find(|(key, _)| *key == path)
        .map(|(_, bytes)| *bytes)
}

pub fn file_icon(path: &str) -> &'static str {
    let extension = Path::new(path)
        .extension()
        .and_then(|ext| ext.to_str())
        .unwrap_or_default()
        .to_ascii_lowercase();
    match extension.as_str() {
        "py" | "pyw" => "icons/languages/python.svg",
        "js" | "jsx" | "mjs" | "cjs" => "icons/languages/javascript.svg",
        "ts" | "tsx" | "mts" | "cts" => "icons/languages/typescript.svg",
        "rs" => "icons/languages/rust.svg",
        "go" => "icons/languages/golang.svg",
        "md" | "markdown" => "icons/languages/markdown.svg",
        _ => "icons/languages/file.svg",
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn embedded_resources_are_unique_and_available_without_filesystem_lookup() {
        let mut keys = std::collections::HashSet::new();
        for (key, bytes) in ICONS {
            assert!(keys.insert(*key), "duplicate resource: {key}");
            assert_eq!(load(key), Some(*bytes));
            assert!(std::str::from_utf8(bytes).unwrap().contains("<svg"));
        }
        assert!(load("/tmp/icons/folder.svg").is_none());
        assert!(load("icons/../settings.json").is_none());
        assert!(load("icons/missing.svg").is_none());
    }
    #[test]
    fn every_embedded_svg_renders_visible_pixels_with_the_gpui_renderer_engine() {
        for (key, bytes) in ICONS {
            let tree = resvg::usvg::Tree::from_data(bytes, &resvg::usvg::Options::default())
                .unwrap_or_else(|error| panic!("{key}: {error}"));
            let mut pixmap = resvg::tiny_skia::Pixmap::new(32, 32).unwrap();
            let size = tree.size();
            let transform =
                resvg::tiny_skia::Transform::from_scale(32. / size.width(), 32. / size.height());
            resvg::render(&tree, transform, &mut pixmap.as_mut());
            assert!(
                pixmap.pixels().iter().any(|pixel| pixel.alpha() > 0),
                "empty icon: {key}"
            );
        }
    }
    #[test]
    fn file_icons_use_extensions_and_always_have_an_embedded_fallback() {
        for (path, expected) in [
            ("中文目录/test.PY", "python"),
            ("src/code.tsx", "typescript"),
            ("test.jsx", "javascript"),
            ("src/main.rs", "rust"),
            ("lib/main.go", "golang"),
            ("README.md", "markdown"),
            ("README", "file"),
            ("some.rs/no-extension", "file"),
            ("source.cpp", "file"),
        ] {
            let icon = file_icon(path);
            assert_eq!(icon, format!("icons/languages/{expected}.svg"));
            assert!(load(icon).is_some());
        }
    }
}
