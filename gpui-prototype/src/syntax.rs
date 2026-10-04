use crate::text::Document;
use std::{
    ops::Range,
    path::Path,
    sync::{Arc, OnceLock},
};
use syntect::{
    easy::ScopeRangeIterator,
    highlighting::{Highlighter, ThemeSet},
    parsing::{ParseState, ScopeStack, SyntaxSet},
};

pub const THEME: &str = "base16-ocean.dark";
pub const PALETTES: [&str; 3] = [THEME, "base16-eighties.dark", "Solarized (dark)"];
pub fn palette_index(name: &str) -> usize {
    PALETTES.iter().position(|p| *p == name).unwrap_or(0)
}
#[derive(Clone, Debug)]
pub struct Token {
    pub range: Range<usize>,
    pub color: u32,
    colors: [u32; 3],
}
impl Token {
    pub fn color_for(&self, palette: usize) -> u32 {
        self.colors.get(palette).copied().unwrap_or(self.color)
    }
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
    let highlighters = PALETTES.map(|name| Highlighter::new(&themes.themes[name]));
    let mut parser = ParseState::new(syntax);
    let mut stack = ScopeStack::new();
    let mut cache = std::collections::HashMap::new();
    let lines = document
        .lines
        .iter()
        .enumerate()
        .map(|(i, range)| {
            let text = &document.text[range.clone()];
            let visible_len = document.display_range(i).len();
            let Ok(ops) = parser.parse_line(text, syntaxes) else {
                return vec![Token {
                    range: 0..visible_len,
                    color: 0xdce5f3,
                    colors: [0xdce5f3; 3],
                }];
            };
            let mut result = vec![];
            for (range, op) in ScopeRangeIterator::new(&ops, text) {
                if stack.apply(op).is_err() {
                    continue;
                }
                if range.is_empty() || range.start >= visible_len {
                    continue;
                }
                let colors = *cache.entry(stack.as_slice().to_vec()).or_insert_with(|| {
                    std::array::from_fn(|i| {
                        let color = highlighters[i].style_for_stack(stack.as_slice()).foreground;
                        ((color.r as u32) << 16) | ((color.g as u32) << 8) | color.b as u32
                    })
                });
                result.push(Token {
                    range: range.start..range.end.min(visible_len),
                    color: colors[0],
                    colors,
                });
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
    fn palettes_preserve_ranges_and_multiline_context() {
        let doc = Document::new("/* 中文🙂\r\n middle */\r\nlet x = \"value\";\r\n");
        let h = highlight(&doc, "file.rs");
        for index in 0..PALETTES.len() {
            assert_eq!(
                h.lines[0][0].color_for(index),
                h.lines[1][0].color_for(index)
            );
            for (line, tokens) in h.lines.iter().enumerate() {
                assert_eq!(
                    tokens.iter().map(|t| t.range.len()).sum::<usize>(),
                    doc.display_range(line).len()
                );
            }
        }
        assert!(
            h.lines
                .iter()
                .flatten()
                .any(|t| t.color_for(0) != t.color_for(1))
        );
        assert_eq!(palette_index("unsupported"), 0);
        assert_eq!(h.lines[0][0].color_for(99), h.lines[0][0].color);
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
