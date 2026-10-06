use crate::{app::*, views::button};
use gpui::{prelude::*, *};
use mygit_gpui::{
    editor::{Buffer, to_utf16, utf16_range},
    syntax::{self, Highlighted},
    text::{DisplayLine, Motion, Side},
};
use std::{
    collections::{BTreeMap, HashMap},
    ops::Range,
};
pub struct CodePalette(pub usize);
impl gpui::Global for CodePalette {}
actions!(
    editor_ui,
    [
        EditorBackspace,
        EditorDelete,
        EditorPaste,
        EditorCut,
        EditorUndo,
        EditorRedo,
        EditorSave,
        InsertNewline,
        InsertTab,
        FindText,
        FindNext,
        FindPrevious,
        CloseFind
    ]
);
pub enum Changed {
    Edited,
    Saved,
    SearchNext,
}
struct Hit {
    range: Range<usize>,
    display: DisplayLine,
    line: ShapedLine,
    bounds: Bounds<Pixels>,
    origin: Point<Pixels>,
}
pub struct Editor {
    pub buffer: Buffer,
    pub focus: FocusHandle,
    pub font_family: String,
    pub font_size: f32,
    pub message: String,
    pub saving: bool,
    external_changed: bool,
    pub reference: mygit_gpui::text::Document,
    pub show_blame: bool,
    pub blame_lines: std::sync::Arc<Vec<mygit_gpui::blame::Line>>,
    pub blame_owner: Option<WeakEntity<MyGit>>,
    pub compact: bool,
    pub form_input: bool,
    form_width: Pixels,
    form_rows: Vec<Range<usize>>,
    pub show_toolbar: bool,
    pub sensitive: bool,
    query: Option<Entity<Editor>>,
    query_subscription: Option<Subscription>,
    matches: Vec<Range<usize>>,
    current_match: Option<usize>,
    marks: std::sync::Arc<BTreeMap<usize, mygit_gpui::editor::LineMark>>,
    generation: u64,
    syntax: Highlighted,
    scroll: UniformListScrollHandle,
    horizontal: f32,
    hits: HashMap<usize, Hit>,
    dragging: bool,
}
impl EventEmitter<Changed> for Editor {}
impl Editor {
    pub fn new(
        buffer: Buffer,
        font_family: String,
        font_size: f32,
        cx: &mut Context<Self>,
    ) -> Self {
        if buffer.path.is_some() {
            cx.spawn(async move |this, cx| {
                loop {
                    Timer::after(std::time::Duration::from_secs(2)).await;
                    let (snapshot, generation) = match this.update(cx, |this, _| {
                        (this.buffer.external_snapshot(), this.generation)
                    }) {
                        Ok((Some(snapshot), generation)) => (snapshot, generation),
                        _ => break,
                    };
                    let task = cx
                        .background_executor()
                        .spawn(async move { snapshot.load_changed() });
                    let result = task.await;
                    if this
                        .update(cx, |this, cx| {
                            if this.generation != generation {
                                return;
                            }
                            let changed = !matches!(&result, Ok(None));
                            if let Ok(Some(replacement)) = result
                                && this.buffer.accept_external(replacement)
                            {
                                this.external_changed = false;
                                this.refresh(cx);
                                return;
                            }
                            if this.external_changed != changed {
                                this.external_changed = changed;
                                cx.notify();
                            }
                        })
                        .is_err()
                    {
                        break;
                    }
                }
            })
            .detach();
        }
        Self {
            buffer,
            focus: cx.focus_handle(),
            font_family,
            font_size,
            message: String::new(),
            saving: false,
            external_changed: false,
            reference: Default::default(),
            compact: false,
            form_input: false,
            form_width: px(240.),
            form_rows: vec![],
            show_toolbar: false,
            sensitive: false,
            show_blame: false,
            blame_lines: Default::default(),
            blame_owner: None,
            query: None,
            query_subscription: None,
            matches: vec![],
            current_match: None,
            marks: Default::default(),
            generation: 0,
            syntax: Default::default(),
            scroll: UniformListScrollHandle::new(),
            horizontal: 0.,
            hits: HashMap::new(),
            dragging: false,
        }
    }
    pub fn replace_all(&mut self, text: &str, cx: &mut Context<Self>) -> anyhow::Result<()> {
        if self.buffer.marked.is_some() {
            anyhow::bail!("请先完成输入法组合");
        }
        self.buffer
            .replace(Some(0..self.buffer.text().len()), text)?;
        self.refresh(cx);
        Ok(())
    }
    pub fn refresh(&mut self, cx: &mut Context<Self>) {
        self.generation += 1;
        if self.sensitive {
            self.syntax = Highlighted::default();
            self.matches.clear();
            self.reveal();
            cx.emit(Changed::Edited);
            cx.notify();
            return;
        }
        let generation = self.generation;
        let document = self.buffer.document.clone();
        let reference = self.reference.clone();
        let compact = self.compact;
        if let Some(query) = &self.query {
            self.matches =
                mygit_gpui::editor::find(self.buffer.text(), query.read(cx).buffer.text());
        }
        let path = self
            .buffer
            .path
            .as_ref()
            .map(|p| p.to_string_lossy().to_string())
            .unwrap_or_default();
        self.syntax = Highlighted::default();
        let task = cx.background_executor().spawn(async move {
            (
                syntax::highlight(&document, &path),
                if compact {
                    BTreeMap::new()
                } else {
                    mygit_gpui::editor::line_marks(&reference.text, &document.text)
                },
            )
        });
        cx.spawn(async move |this, cx| {
            let (syntax, marks) = task.await;
            let _ = this.update(cx, |this, cx| {
                if this.generation == generation {
                    this.syntax = syntax;
                    this.marks = std::sync::Arc::new(marks);
                    cx.notify();
                }
            });
        })
        .detach();
        self.reveal();
        cx.emit(Changed::Edited);
        cx.notify();
    }
    pub fn select_matching_document(
        &mut self,
        document: &mygit_gpui::text::Document,
        selection: &mygit_gpui::text::TextSelection,
        cx: &mut Context<Self>,
    ) -> bool {
        if !self.buffer.select_matching_document(document, selection) {
            return false;
        }
        self.reveal();
        cx.notify();
        true
    }
    fn reveal(&mut self) {
        self.scroll
            .scroll_to_item(self.caret_line(), ScrollStrategy::Center);
    }
    fn caret_line(&self) -> usize {
        if self.form_input && !self.compact && !self.form_rows.is_empty() {
            return self
                .form_rows
                .iter()
                .rposition(|range| range.start <= self.buffer.selection.head)
                .unwrap_or(0);
        }
        if self.buffer.selection.head == self.buffer.text().len()
            && self.buffer.text().ends_with('\n')
        {
            self.buffer.document.lines.len()
        } else {
            self.buffer.document.line_index(self.buffer.selection.head)
        }
    }
    fn result(&mut self, result: anyhow::Result<()>, cx: &mut Context<Self>) {
        match result {
            Ok(()) => {
                self.message.clear();
                self.refresh(cx);
            }
            Err(e) => {
                self.message = format!("{e:#}");
                cx.notify();
            }
        }
    }
    fn insert(&mut self, text: &str, cx: &mut Context<Self>) {
        let result = self.buffer.paste(text);
        self.result(result, cx);
    }
    fn motion(&mut self, motion: Motion, extend: bool, cx: &mut Context<Self>) {
        if self.form_input && !self.compact && matches!(motion, Motion::Up | Motion::Down) {
            let row = self.caret_line();
            let next = if matches!(motion, Motion::Up) {
                row.saturating_sub(1)
            } else {
                (row + 1).min(self.form_rows.len().saturating_sub(1))
            };
            if let (Some(current), Some(target)) = (self.hits.get(&row), self.hits.get(&next)) {
                let local = self
                    .buffer
                    .selection
                    .head
                    .saturating_sub(current.range.start)
                    .min(current.range.len());
                let x = current
                    .line
                    .x_for_index(current.display.display_offset(local));
                let offset = target.range.start
                    + target
                        .display
                        .source_offset(target.line.closest_index_for_x(x));
                self.buffer.finish_composition();
                self.buffer
                    .selection
                    .point(Side::Right, offset, extend, &self.buffer.document);
                self.reveal();
                cx.notify();
                return;
            }
        }
        self.buffer.move_cursor(motion, extend);
        self.reveal();
        cx.notify();
    }
    fn copy(&mut self, cx: &mut Context<Self>) {
        if self.sensitive {
            return;
        }
        if let Some(text) = self.buffer.selection.copy(&self.buffer.document) {
            cx.write_to_clipboard(ClipboardItem::new_string(text));
        }
    }
    fn paste(&mut self, cx: &mut Context<Self>) {
        if let Some(text) = cx.read_from_clipboard().and_then(|c| c.text()) {
            self.insert(&text, cx);
        }
    }
    pub fn save(&mut self, cx: &mut Context<Self>) {
        if self.saving {
            return;
        }
        // The file is at most 2 MB. Conflict checks and atomic replacement are in Buffer.
        self.saving = true;
        let result = self.buffer.save();
        self.saving = false;
        match result {
            Ok(()) => self.message = mygit_gpui::i18n::text("已保存").into(),
            Err(e) => self.message = format!("{e:#}"),
        };
        cx.emit(Changed::Saved);
        cx.notify();
    }
    pub fn reload(&mut self, cx: &mut Context<Self>) {
        if self.buffer.dirty() {
            self.message =
                mygit_gpui::i18n::text("当前内容未保存，请先保存或关闭后重新打开").into();
            cx.notify();
            return;
        }
        if let Some(path) = self.buffer.path.clone() {
            match Buffer::load(&path) {
                Ok(buffer) => {
                    if self.buffer.accept_external(buffer) {
                        self.external_changed = false;
                        self.refresh(cx);
                    } else {
                        self.message =
                            mygit_gpui::i18n::text("文件目标已变化或正在输入，请关闭后重新打开")
                                .into();
                        cx.notify();
                    }
                }
                Err(e) => {
                    self.message = format!("{e:#}");
                    cx.notify();
                }
            }
        }
    }
    fn show_find(&mut self, window: &mut Window, cx: &mut Context<Self>) {
        if self.compact || self.sensitive {
            return;
        }
        if self.query.is_none() {
            let text = self
                .buffer
                .selection
                .copy(&self.buffer.document)
                .unwrap_or_default();
            let font = self.font_family.clone();
            let size = self.font_size;
            let query = cx.new(|cx| {
                let mut editor = Editor::new(Buffer::new(&text), font, size, cx);
                editor.compact = true;
                editor
            });
            self.query_subscription =
                Some(cx.subscribe(&query, |this, query, event: &Changed, cx| {
                    if matches!(event, Changed::SearchNext) {
                        this.find_move(true, cx);
                        return;
                    }
                    let query = query.read(cx).buffer.text().to_owned();
                    this.matches = mygit_gpui::editor::find(this.buffer.text(), &query);
                    this.current_match = None;
                    cx.notify();
                }));
            self.matches = mygit_gpui::editor::find(self.buffer.text(), &text);
            self.query = Some(query);
        }
        if let Some(query) = &self.query {
            window.focus(&query.read(cx).focus);
        }
        cx.notify();
    }
    fn find_move(&mut self, forward: bool, cx: &mut Context<Self>) {
        if self.matches.is_empty() {
            self.current_match = None;
            cx.notify();
            return;
        }
        let i = match self.current_match {
            None => {
                if forward {
                    0
                } else {
                    self.matches.len() - 1
                }
            }
            Some(i) => {
                if forward {
                    (i + 1) % self.matches.len()
                } else {
                    (i + self.matches.len() - 1) % self.matches.len()
                }
            }
        };
        self.current_match = Some(i);
        let range = self.matches[i].clone();
        self.buffer.selection.anchor = range.start;
        self.buffer.selection.head = range.end;
        self.reveal();
        cx.notify();
    }
    fn hit_offset(&self, position: Point<Pixels>) -> Option<usize> {
        self.hits
            .values()
            .min_by(|a, b| {
                let distance = |h: &Hit| {
                    if position.y < h.bounds.top() {
                        h.bounds.top() - position.y
                    } else if position.y > h.bounds.bottom() {
                        position.y - h.bounds.bottom()
                    } else {
                        px(0.)
                    }
                };
                distance(a)
                    .partial_cmp(&distance(b))
                    .unwrap_or(std::cmp::Ordering::Equal)
            })
            .map(|h| {
                h.range.start
                    + h.display
                        .source_offset(h.line.closest_index_for_x(position.x - h.origin.x))
            })
    }
    fn mouse_down(&mut self, event: &MouseDownEvent, window: &mut Window, cx: &mut Context<Self>) {
        cx.stop_propagation();
        window.focus(&self.focus);
        cx.activate(true);
        self.buffer.finish_composition();
        self.dragging = true;
        if let Some(offset) = self.hit_offset(event.position) {
            self.buffer.selection.point(
                Side::Right,
                offset,
                event.modifiers.shift,
                &self.buffer.document,
            );
            cx.notify();
        }
    }
    fn mouse_move(&mut self, event: &MouseMoveEvent, _: &mut Window, cx: &mut Context<Self>) {
        if self.dragging
            && let Some(offset) = self.hit_offset(event.position)
        {
            self.buffer
                .selection
                .point(Side::Right, offset, true, &self.buffer.document);
            cx.notify();
        }
    }
}
impl Focusable for Editor {
    fn focus_handle(&self, _: &App) -> FocusHandle {
        self.focus.clone()
    }
}
impl EntityInputHandler for Editor {
    fn text_for_range(
        &mut self,
        range: Range<usize>,
        actual: &mut Option<Range<usize>>,
        _: &mut Window,
        _: &mut Context<Self>,
    ) -> Option<String> {
        if self.sensitive {
            return None;
        }
        let range = utf16_range(self.buffer.text(), range);
        *actual = Some(
            to_utf16(self.buffer.text(), range.start)..to_utf16(self.buffer.text(), range.end),
        );
        Some(self.buffer.text()[range].into())
    }
    fn selected_text_range(
        &mut self,
        _: bool,
        _: &mut Window,
        _: &mut Context<Self>,
    ) -> Option<UTF16Selection> {
        let range = self.buffer.selection.range();
        Some(UTF16Selection {
            range: to_utf16(self.buffer.text(), range.start)
                ..to_utf16(self.buffer.text(), range.end),
            reversed: self.buffer.selection.head < self.buffer.selection.anchor,
        })
    }
    fn marked_text_range(&self, _: &mut Window, _: &mut Context<Self>) -> Option<Range<usize>> {
        self.buffer
            .marked
            .as_ref()
            .map(|r| to_utf16(self.buffer.text(), r.start)..to_utf16(self.buffer.text(), r.end))
    }
    fn unmark_text(&mut self, _: &mut Window, cx: &mut Context<Self>) {
        self.buffer.finish_composition();
        cx.emit(Changed::Edited);
        cx.notify();
    }
    fn replace_text_in_range(
        &mut self,
        range: Option<Range<usize>>,
        text: &str,
        _: &mut Window,
        cx: &mut Context<Self>,
    ) {
        let range = range.map(|r| utf16_range(self.buffer.text(), r));
        let result = self.buffer.replace(range, text);
        self.result(result, cx);
    }
    fn replace_and_mark_text_in_range(
        &mut self,
        range: Option<Range<usize>>,
        text: &str,
        selected: Option<Range<usize>>,
        _: &mut Window,
        cx: &mut Context<Self>,
    ) {
        let range = range.map(|r| utf16_range(self.buffer.text(), r));
        let result = self.buffer.compose(range, text, selected);
        self.result(result, cx);
    }
    fn bounds_for_range(
        &mut self,
        range: Range<usize>,
        _: Bounds<Pixels>,
        _: &mut Window,
        _: &mut Context<Self>,
    ) -> Option<Bounds<Pixels>> {
        let range = utf16_range(self.buffer.text(), range);
        let hit = self.hits.get(&self.caret_line())?;
        let a = range
            .start
            .saturating_sub(hit.range.start)
            .min(hit.range.len());
        let b = range
            .end
            .saturating_sub(hit.range.start)
            .min(hit.range.len());
        let x1 = hit.line.x_for_index(hit.display.display_offset(a));
        let x2 = hit.line.x_for_index(hit.display.display_offset(b));
        Some(Bounds::new(
            point(hit.origin.x + x1, hit.bounds.top()),
            size((x2 - x1).max(px(1.)), hit.bounds.size.height),
        ))
    }
    fn character_index_for_point(
        &mut self,
        point: Point<Pixels>,
        _: &mut Window,
        _: &mut Context<Self>,
    ) -> Option<usize> {
        self.hit_offset(point)
            .map(|offset| to_utf16(self.buffer.text(), offset))
    }
}
fn line(this: &Editor, index: usize, cx: &mut Context<Editor>) -> impl IntoElement {
    let palette = cx.try_global::<CodePalette>().map_or(0, |p| p.0);
    let range = if this.form_input && !this.compact {
        this.form_rows
            .get(index)
            .cloned()
            .unwrap_or(this.buffer.text().len()..this.buffer.text().len())
    } else {
        this.buffer.document.display_range(index)
    };
    let display = if this.sensitive {
        DisplayLine::masked(&this.buffer.text()[range.clone()])
    } else {
        DisplayLine::new(&this.buffer.text()[range.clone()])
    };
    let tokens = if this.sensitive || this.form_input {
        vec![]
    } else {
        this.syntax.lines.get(index).cloned().unwrap_or_default()
    };
    let selection = this.buffer.selection.range();
    let matches = this
        .matches
        .iter()
        .filter(|found| found.start < range.end && found.end > range.start)
        .cloned()
        .collect::<Vec<_>>();
    let marked = this.buffer.marked.clone();
    let caret = this.buffer.selection.head;
    let horizontal = this.horizontal;
    let entity = cx.entity();
    let newline_selected = this
        .buffer
        .document
        .lines
        .get(index)
        .is_some_and(|r| selection.end >= r.end && selection.start < r.end);
    canvas(
        move |_, window, _| {
            let style = window.text_style();
            let font = style.font();
            let mut runs: Vec<_> = tokens
                .iter()
                .filter_map(|t| {
                    let len =
                        display.display_offset(t.range.end) - display.display_offset(t.range.start);
                    (len > 0).then(|| TextRun {
                        len,
                        font: font.clone(),
                        color: rgb(t.color_for(palette)).into(),
                        background_color: None,
                        underline: None,
                        strikethrough: None,
                    })
                })
                .collect();
            if runs.is_empty() {
                runs.push(TextRun {
                    len: display.text.len(),
                    font,
                    color: rgb(0x202020).into(),
                    background_color: None,
                    underline: None,
                    strikethrough: None,
                });
            }
            let line = window.text_system().shape_line(
                display.text.clone().into(),
                style.font_size.to_pixels(window.rem_size()),
                &runs,
                None,
            );
            (line, display)
        },
        move |bounds, (line, display), window, cx| {
            let origin = point(bounds.left() - px(horizontal), bounds.top());
            let visible = window.content_mask().bounds.intersect(&bounds);
            window.with_content_mask(Some(ContentMask { bounds }), |window| {
                for found in &matches {
                    if found.start < range.end && found.end > range.start {
                        let a = found.start.saturating_sub(range.start).min(range.len());
                        let b = found.end.saturating_sub(range.start).min(range.len());
                        let x1 = line.x_for_index(display.display_offset(a));
                        let x2 = line.x_for_index(display.display_offset(b));
                        window.paint_quad(fill(
                            Bounds::new(
                                point(origin.x + x1, bounds.top()),
                                size(x2 - x1, bounds.size.height),
                            ),
                            rgb(0x66552c),
                        ));
                    }
                }
                if selection.start <= range.end
                    && selection.end > range.start
                    && !selection.is_empty()
                {
                    let a = selection.start.saturating_sub(range.start).min(range.len());
                    let b = selection.end.saturating_sub(range.start).min(range.len());
                    let x1 = line.x_for_index(display.display_offset(a));
                    let x2 = line.x_for_index(display.display_offset(b))
                        + if newline_selected { px(8.) } else { px(0.) };
                    window.paint_quad(fill(
                        Bounds::new(
                            point(origin.x + x1, bounds.top()),
                            size((x2 - x1).max(px(0.)), bounds.size.height),
                        ),
                        rgb(0xb5d6fa),
                    ));
                }
                if let Some(marked) = &marked
                    && marked.start < range.end
                    && marked.end > range.start
                {
                    let a = marked.start.saturating_sub(range.start).min(range.len());
                    let b = marked.end.saturating_sub(range.start).min(range.len());
                    let x1 = line.x_for_index(display.display_offset(a));
                    let x2 = line.x_for_index(display.display_offset(b));
                    window.paint_quad(fill(
                        Bounds::new(
                            point(origin.x + x1, bounds.bottom() - px(2.)),
                            size(x2 - x1, px(1.)),
                        ),
                        rgb(0x946200),
                    ));
                }
                let _ = line.paint(origin, bounds.size.height, window, cx);
                if selection.is_empty()
                    && caret >= range.start
                    && caret <= range.end
                    && entity.read(cx).focus.is_focused(window)
                {
                    let x = line.x_for_index(display.display_offset(caret - range.start));
                    window.paint_quad(fill(
                        Bounds::new(
                            point(origin.x + x, bounds.top() + px(2.)),
                            size(px(1.), bounds.size.height - px(4.)),
                        ),
                        rgb(0x202020),
                    ));
                }
            });
            entity.update(cx, |this, _| {
                this.hits.insert(
                    index,
                    Hit {
                        range,
                        display,
                        line,
                        bounds: visible,
                        origin,
                    },
                );
            });
        },
    )
    .w_full()
    .h_full()
}
fn overview(editor: &Editor) -> impl IntoElement {
    let marks = editor.marks.clone();
    let count = (editor.buffer.document.lines.len()
        + usize::from(editor.buffer.text().ends_with('\n')))
    .max(1);
    canvas(
        |_, _, _| (),
        move |bounds, _, window, _| {
            let height = f32::from(bounds.size.height).max(0.);
            // Aggregate into pixel bands: overlapping lines use deleted > modified > added.
            let mut bands = vec![0u8; (height.ceil() as usize).min(8192)];
            for (line, mark) in marks.iter() {
                let index = ((*line).min(count - 1) as f32 / count as f32 * height) as usize;
                let priority = if mark.deleted > 0 {
                    3
                } else if mark.modified {
                    2
                } else if mark.added {
                    1
                } else {
                    0
                };
                if let Some(band) = bands.get_mut(index) {
                    *band = (*band).max(priority);
                }
            }
            for (index, priority) in bands.into_iter().enumerate() {
                let color = match priority {
                    3 => 0xf44336,
                    2 => 0xffc107,
                    1 => 0x4caf50,
                    _ => continue,
                };
                let y = index as f32;
                window.paint_quad(fill(
                    Bounds::new(
                        point(bounds.left() + px(2.), bounds.top() + px(y)),
                        size(
                            px(6.),
                            px((height / count as f32).max(3.).min((height - y).max(0.))),
                        ),
                    ),
                    rgb(color),
                ));
            }
        },
    )
    .w(px(10.))
    .h_full()
    .flex_shrink_0()
}

impl Render for Editor {
    fn render(&mut self, window: &mut Window, cx: &mut Context<Self>) -> impl IntoElement {
        if self.form_input && !self.compact {
            use unicode_segmentation::UnicodeSegmentation;
            self.form_rows.clear();
            for i in 0..self.buffer.document.lines.len() {
                let range = self.buffer.document.display_range(i);
                let text = &self.buffer.text()[range.clone()];
                let display = DisplayLine::new(text);
                let shaped = window.text_system().shape_line(
                    display.text.clone().into(),
                    px(self.font_size),
                    &[TextRun {
                        len: display.text.len(),
                        font: font(self.font_family.clone()),
                        color: rgb(0x202020).into(),
                        background_color: None,
                        underline: None,
                        strikethrough: None,
                    }],
                    None,
                );
                let mut start = 0;
                for (offset, grapheme) in text.grapheme_indices(true) {
                    let end = offset + grapheme.len();
                    if offset > start
                        && shaped.x_for_index(display.display_offset(end))
                            - shaped.x_for_index(display.display_offset(start))
                            > self.form_width
                    {
                        self.form_rows
                            .push(range.start + start..range.start + offset);
                        start = offset;
                    }
                }
                self.form_rows.push(range.start + start..range.end);
            }
            if self.buffer.text().ends_with('\n') {
                self.form_rows
                    .push(self.buffer.text().len()..self.buffer.text().len());
            }
        }
        let weak = cx.entity().downgrade();
        let scroll_listener = canvas(
            |_, _, _| (),
            move |_, _, window, _| {
                window.on_mouse_event(move |event: &ScrollWheelEvent, phase, _, cx| {
                    if phase != DispatchPhase::Capture {
                        return;
                    }
                    let _ = weak.update(cx, |this, cx| {
                        if !this
                            .hits
                            .values()
                            .any(|h| h.bounds.contains(&event.position))
                        {
                            return;
                        }
                        let delta = event.delta.pixel_delta(px(this.font_size + 6.));
                        let dx = if event.modifiers.shift && delta.x == px(0.) {
                            delta.y
                        } else {
                            delta.x
                        };
                        if dx != px(0.) && !(this.form_input && !this.compact) {
                            let visible = this
                                .hits
                                .values()
                                .map(|h| f32::from(h.bounds.size.width))
                                .fold(0., f32::max);
                            let longest = this
                                .buffer
                                .text()
                                .lines()
                                .map(|s| {
                                    DisplayLine::new(s)
                                        .text
                                        .chars()
                                        .map(|c| if c.is_ascii() { 1 } else { 2 })
                                        .sum::<usize>()
                                })
                                .max()
                                .unwrap_or(0) as f32
                                * this.font_size;
                            this.horizontal = (this.horizontal - f32::from(dx))
                                .clamp(0., (longest - visible).max(0.));
                            cx.stop_propagation();
                            cx.notify();
                        }
                    });
                });
            },
        )
        .absolute()
        .size_full();
        self.hits.clear();
        let entity = cx.entity();
        let focus = self.focus.clone();
        let count = if self.form_input && !self.compact {
            self.form_rows.len()
        } else {
            self.buffer.document.lines.len() + usize::from(self.buffer.text().ends_with('\n'))
        };
        div()
            .relative()
            .bg(rgb(0xffffff))
            .w_full()
            .child(scroll_listener)
            .flex()
            .flex_col()
            .min_h_0()
            .when(!self.compact, |s| s.flex_1())
            .when(self.compact, |s| {
                s.h(px(24.))
                    .flex_shrink_0()
                    .border_1()
                    .border_color(rgb(0xbcbcbc))
                    .bg(rgb(0xffffff))
            })
            .key_context("FileEditor")
            .track_focus(&self.focus)
            .on_mouse_down(MouseButton::Left, cx.listener(Self::mouse_down))
            .on_mouse_move(cx.listener(Self::mouse_move))
            .on_mouse_up(
                MouseButton::Left,
                cx.listener(|this, _, _, _| this.dragging = false),
            )
            .on_mouse_up_out(
                MouseButton::Left,
                cx.listener(|this, _, _, _| this.dragging = false),
            )
            .on_action(cx.listener(|this, _: &FindText, window, cx| this.show_find(window, cx)))
            .on_action(cx.listener(|this, _: &FindNext, _, cx| {
                if this.compact || this.form_input {
                    cx.propagate();
                } else {
                    this.find_move(true, cx);
                }
            }))
            .on_action(cx.listener(|this, _: &FindPrevious, _, cx| {
                if this.compact || this.form_input {
                    cx.propagate();
                } else {
                    this.find_move(false, cx);
                }
            }))
            .on_action(cx.listener(|this, _: &CloseFind, window, cx| {
                if this.compact || this.form_input {
                    cx.propagate();
                    return;
                }
                this.query = None;
                this.query_subscription = None;
                this.matches.clear();
                this.current_match = None;
                window.focus(&this.focus);
                cx.notify();
            }))
            .on_action(cx.listener(|this, _: &CopyText, _, cx| this.copy(cx)))
            .on_action(cx.listener(|this, _: &SelectAllText, _, cx| {
                this.buffer.selection.select_all(&this.buffer.document);
                cx.notify();
            }))
            .on_action(cx.listener(|this, _: &EditorPaste, _, cx| this.paste(cx)))
            .on_action(cx.listener(|this, _: &EditorCut, _, cx| {
                this.copy(cx);
                let result = this.buffer.replace(None, "");
                this.result(result, cx);
            }))
            .on_action(cx.listener(|this, _: &EditorUndo, _, cx| {
                this.buffer.undo();
                this.refresh(cx);
            }))
            .on_action(cx.listener(|this, _: &EditorRedo, _, cx| {
                this.buffer.redo();
                this.refresh(cx);
            }))
            .on_action(cx.listener(|this, _: &EditorSave, _, cx| this.save(cx)))
            .on_action(cx.listener(|this, _: &EditorBackspace, _, cx| {
                let result = this.buffer.delete(true);
                this.result(result, cx);
            }))
            .on_action(cx.listener(|this, _: &EditorDelete, _, cx| {
                let result = this.buffer.delete(false);
                this.result(result, cx);
            }))
            .on_action(cx.listener(|this, _: &InsertNewline, _, cx| {
                if this.compact {
                    cx.emit(Changed::SearchNext);
                } else {
                    this.insert("\n", cx);
                }
            }))
            .on_action(cx.listener(|this, _: &InsertTab, _, cx| {
                if this.form_input {
                    cx.propagate();
                } else {
                    this.insert("\t", cx);
                }
            }))
            .on_action(cx.listener(|this, _: &Left, _, cx| this.motion(Motion::Left, false, cx)))
            .on_action(cx.listener(|this, _: &Right, _, cx| this.motion(Motion::Right, false, cx)))
            .on_action(cx.listener(|this, _: &Up, _, cx| this.motion(Motion::Up, false, cx)))
            .on_action(cx.listener(|this, _: &Down, _, cx| this.motion(Motion::Down, false, cx)))
            .on_action(cx.listener(|this, _: &Home, _, cx| this.motion(Motion::Home, false, cx)))
            .on_action(cx.listener(|this, _: &End, _, cx| this.motion(Motion::End, false, cx)))
            .on_action(cx.listener(|this, _: &Start, _, cx| this.motion(Motion::Start, false, cx)))
            .on_action(
                cx.listener(|this, _: &Finish, _, cx| this.motion(Motion::Finish, false, cx)),
            )
            .on_action(
                cx.listener(|this, _: &SelectLeft, _, cx| this.motion(Motion::Left, true, cx)),
            )
            .on_action(
                cx.listener(|this, _: &SelectRight, _, cx| this.motion(Motion::Right, true, cx)),
            )
            .on_action(cx.listener(|this, _: &SelectUp, _, cx| this.motion(Motion::Up, true, cx)))
            .on_action(
                cx.listener(|this, _: &SelectDown, _, cx| this.motion(Motion::Down, true, cx)),
            )
            .on_action(
                cx.listener(|this, _: &SelectHome, _, cx| this.motion(Motion::Home, true, cx)),
            )
            .on_action(cx.listener(|this, _: &SelectEnd, _, cx| this.motion(Motion::End, true, cx)))
            .on_action(
                cx.listener(|this, _: &SelectStart, _, cx| this.motion(Motion::Start, true, cx)),
            )
            .on_action(
                cx.listener(|this, _: &SelectFinish, _, cx| this.motion(Motion::Finish, true, cx)),
            )
            .when(!self.compact && self.show_toolbar, |s| {
                s.child(
                    div()
                        .flex()
                        .gap_2()
                        .p_2()
                        .when(self.buffer.path.is_some(), |s| {
                            s.child(
                                button("save-editor", mygit_gpui::i18n::text("保存"), !self.saving)
                                    .on_click(cx.listener(|this, _, _, cx| this.save(cx))),
                            )
                            .child(
                                button(
                                    "reload-editor",
                                    mygit_gpui::i18n::text("重新加载"),
                                    !self.buffer.dirty(),
                                )
                                .on_click(cx.listener(|this, _, _, cx| this.reload(cx))),
                            )
                        })
                        .child(
                            button(
                                "undo-editor",
                                mygit_gpui::i18n::text("撤销"),
                                self.buffer.can_undo(),
                            )
                            .on_click(cx.listener(|this, _, _, cx| {
                                this.buffer.undo();
                                this.refresh(cx);
                            })),
                        )
                        .child(
                            button(
                                "redo-editor",
                                mygit_gpui::i18n::text("重做"),
                                self.buffer.can_redo(),
                            )
                            .on_click(cx.listener(|this, _, _, cx| {
                                this.buffer.redo();
                                this.refresh(cx);
                            })),
                        )
                        .child(div().text_color(rgb(0x666666)).child(format!(
                            "{} · {}",
                            if self.buffer.path.is_none() {
                                mygit_gpui::i18n::text("提交信息")
                            } else if self.buffer.dirty() {
                                mygit_gpui::i18n::text("未保存")
                            } else {
                                mygit_gpui::i18n::text("已保存")
                            },
                            if self.buffer.crlf { "CRLF" } else { "LF" }
                        ))),
                )
            })
            .when(self.external_changed, |s| {
                s.child(
                    div()
                        .p_2()
                        .text_color(rgb(0x946200))
                        .child(mygit_gpui::i18n::text(
                            "磁盘文件已变化。保存会检查冲突；无未保存修改时可重新加载。",
                        )),
                )
            })
            .when(!self.message.is_empty(), |s| {
                s.child(
                    div()
                        .p_2()
                        .text_color(rgb(0x946200))
                        .child(self.message.clone()),
                )
            })
            .when_some(self.query.clone(), |s, query| {
                s.child(
                    div()
                        .flex()
                        .items_center()
                        .gap_2()
                        .p_2()
                        .child(div().flex_1().min_w_0().h(px(32.)).child(query))
                        .child(div().child(format!(
                            "{} / {}",
                            self.current_match.map(|i| i + 1).unwrap_or(0),
                            self.matches.len()
                        )))
                        .child(
                            button(
                                "previous-match",
                                mygit_gpui::i18n::text("上一处"),
                                !self.matches.is_empty(),
                            )
                            .on_click(cx.listener(|this, _, _, cx| this.find_move(false, cx))),
                        )
                        .child(
                            button(
                                "next-match",
                                mygit_gpui::i18n::text("下一处"),
                                !self.matches.is_empty(),
                            )
                            .on_click(cx.listener(|this, _, _, cx| this.find_move(true, cx))),
                        )
                        .child(
                            button("close-find", mygit_gpui::i18n::text("关闭查找"), true)
                                .on_click(cx.listener(|this, _, _, cx| {
                                    this.query = None;
                                    this.query_subscription = None;
                                    this.matches.clear();
                                    cx.notify();
                                })),
                        ),
                )
            })
            .child(
                div()
                    .flex()
                    .flex_1()
                    .min_h_0()
                    .min_w_0()
                    .child(
                        uniform_list(
                            "editor-lines",
                            count.max(1),
                            cx.processor(|this, range: Range<usize>, _, cx| {
                                range
                                    .map(|i| {
                                        div()
                                            .id(("editor-line", i))
                                            .w_full()
                                            .flex()
                                            .h(px(this.font_size + 6.))
                                            .font_family(this.font_family.clone())
                                            .text_size(px(this.font_size))
                                            .when(!this.compact && !this.form_input, |s| {
                                                s.child(
                                                    div()
                                                        .w(px(52.))
                                                        .flex_shrink_0()
                                                        .text_color(rgb(0x888888))
                                                        .child(format!(
                                                            "{} {}",
                                                            this.marks
                                                                .get(&i)
                                                                .map(|m| if m.deleted > 0 {
                                                                    format!("−{}", m.deleted)
                                                                } else if m.added {
                                                                    "+".into()
                                                                } else {
                                                                    "~".into()
                                                                })
                                                                .unwrap_or_default(),
                                                            i + 1
                                                        )),
                                                )
                                            })
                                            .when(this.show_blame && !this.compact, |s| {
                                                if let Some(owner) = &this.blame_owner {
                                                    s.child(crate::views::blame::gutter(
                                                        owner.clone(),
                                                        this.blame_lines.get(i).cloned(),
                                                        i,
                                                    ))
                                                } else {
                                                    s
                                                }
                                            })
                                            .child(
                                                div()
                                                    .min_w_0()
                                                    .flex_1()
                                                    .h_full()
                                                    .overflow_hidden()
                                                    .child(line(this, i, cx)),
                                            )
                                    })
                                    .collect::<Vec<_>>()
                            }),
                        )
                        .track_scroll(self.scroll.clone())
                        .w_full()
                        .flex_1()
                        .min_h_0(),
                    )
                    .when(
                        !self.compact && !self.sensitive && self.buffer.path.is_some(),
                        |s| s.child(overview(self)),
                    ),
            )
            .child(
                canvas(
                    |_, _, _| (),
                    move |bounds, _, window, cx| {
                        entity.update(cx, |editor, cx| {
                            if editor.form_input
                                && !editor.compact
                                && (editor.form_width - bounds.size.width).abs() > px(1.)
                            {
                                editor.form_width = bounds.size.width;
                                cx.notify();
                            }
                        });
                        window.handle_input(&focus, ElementInputHandler::new(bounds, entity), cx);
                    },
                )
                .absolute()
                .size_full(),
            )
    }
}
