use crate::text::Document;
use std::{
    ops::Range,
    path::Path,
    sync::{Arc, OnceLock},
};
use syntect::{easy::HighlightLines, highlighting::ThemeSet, parsing::SyntaxSet};

pub const THEME: &str = "base16-ocean.dark";
#[derive(Clone, Debug)]
pub struct Token {
    pub range: Range<usize>,
    pub color: u32,
}
#[derive(Clone, Debug, Default)]
pub struct Highlighted {
    pub language: String,
    pub lines: Arc<Vec<Vec<Token>>>,
}
pub fn highlight(document: &Document, path: &str) -> Highlighted {
    static SYNTAXES: OnceLock<SyntaxSet> = OnceLock::new();
    static THEMES: OnceLock<ThemeSet> = OnceLock::new();
    let syntaxes = SYNTAXES.get_or_init(SyntaxSet::load_defaults_newlines);
    let themes = THEMES.get_or_init(ThemeSet::load_defaults);
    let extension = Path::new(path)
        .extension()
        .and_then(|s| s.to_str())
        .unwrap_or("");
    let syntax = syntaxes
        .find_syntax_by_extension(extension)
        .or_else(|| {
            document
                .text
                .lines()
                .next()
                .and_then(|line| syntaxes.find_syntax_by_first_line(line))
        })
        .unwrap_or_else(|| syntaxes.find_syntax_plain_text());
    let mut highlighter = HighlightLines::new(syntax, &themes.themes[THEME]);
    let lines = document
        .lines
        .iter()
        .enumerate()
        .map(|(i, range)| {
            let text = &document.text[range.clone()];
            let visible_len = document.display_range(i).len();
            let Ok(tokens) = highlighter.highlight_line(text, syntaxes) else {
                return vec![Token {
                    range: 0..visible_len,
                    color: 0xdce5f3,
                }];
            };
            let mut offset = 0;
            let mut result = vec![];
            for (style, text) in tokens {
                let end = offset + text.len();
                if offset < visible_len {
                    let color = style.foreground;
                    result.push(Token {
                        range: offset..end.min(visible_len),
                        color: ((color.r as u32) << 16) | ((color.g as u32) << 8) | color.b as u32,
                    });
                }
                offset = end;
            }
            result
        })
        .collect();
    Highlighted {
        language: syntax.name.clone(),
        lines: Arc::new(lines),
    }
}
#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn supported_languages_have_colored_tokens_and_exact_ranges() {
        for (path, text, name) in [
            ("file.rs", "fn main() { let value = \"中文🙂\"; }\n", "Rust"),
            ("file.py", "def hello():\n    return \"中文🙂\"\n", "Python"),
            (
                "file.js",
                "function hello() { return \"中文🙂\"; }\n",
                "JavaScript",
            ),
        ] {
            let document = Document::new(text);
            let highlighted = highlight(&document, path);
            assert_eq!(highlighted.language, name);
            let colors: std::collections::HashSet<_> = highlighted
                .lines
                .iter()
                .flatten()
                .map(|t| t.color)
                .collect();
            assert!(colors.len() >= 2);
            for (i, tokens) in highlighted.lines.iter().enumerate() {
                assert_eq!(
                    tokens.iter().map(|t| t.range.len()).sum::<usize>(),
                    document.display_range(i).len()
                );
                assert!(tokens.iter().all(|t| {
                    document.text[document.display_range(i)].is_char_boundary(t.range.start)
                }));
            }
        }
    }
    #[test]
    fn multiline_context_and_plain_text_fallback() {
        let document = Document::new("/* start\n   middle\n*/\nlet x = 1;\n");
        let h = highlight(&document, "file.rs");
        assert_eq!(h.lines[0][0].color, h.lines[1][0].color);
        assert_ne!(h.lines[1][0].color, h.lines[3][0].color);
        assert_eq!(
            highlight(&Document::new("plain\n"), "file.unknownextension").language,
            "Plain Text"
        );
    }
}
