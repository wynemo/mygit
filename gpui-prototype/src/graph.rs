//! Prefix-stable lane layout. Every row owns half of its incoming/outgoing edges,
//! so virtual rows can be painted independently without spanning elements.
use crate::model::Commit;
use std::collections::HashSet;

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Edge {
    pub from: usize,
    pub to: usize,
    pub color: usize,
    pub incoming: bool,
    pub continuation: bool,
}
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Row {
    pub lane: usize,
    pub color: usize,
    pub edges: Vec<Edge>,
    pub columns: usize,
    /// Parents omitted by a search/path filter, never connected to an unrelated row.
    pub omitted: usize,
}
#[derive(Clone)]
struct Lane {
    sha: String,
    color: usize,
}
/// No lookahead for ordinary history: appending pages cannot change existing rows.
/// Filtered lists draw stubs for parents absent from the displayed result.
pub fn layout(commits: &[Commit], filtered: bool) -> Vec<Row> {
    let visible: HashSet<_> = commits.iter().map(|c| c.sha.as_str()).collect();
    let mut lanes: Vec<Option<Lane>> = vec![];
    let mut next_color = 0;
    let mut rows = Vec::with_capacity(commits.len());
    for commit in commits {
        let existing = lanes
            .iter()
            .any(|l| l.as_ref().is_some_and(|l| l.sha == commit.sha));
        let lane = lanes
            .iter()
            .position(|l| l.as_ref().is_some_and(|l| l.sha == commit.sha))
            .unwrap_or_else(|| {
                let index = vacant(&mut lanes);
                lanes[index] = Some(Lane {
                    sha: commit.sha.clone(),
                    color: next_color,
                });
                next_color += 1;
                index
            });
        let color = lanes[lane].as_ref().unwrap().color;
        let mut edges: Vec<_> = lanes
            .iter()
            .enumerate()
            .filter_map(|(i, l)| {
                if i == lane && !existing {
                    return None;
                }
                l.as_ref().map(|l| Edge {
                    from: i,
                    to: i,
                    color: l.color,
                    incoming: true,
                    continuation: i != lane,
                })
            })
            .collect();
        lanes[lane] = None;
        let mut seen = HashSet::new();
        let mut omitted = 0;
        for (p, parent) in commit
            .parents
            .iter()
            .filter(|p| seen.insert(p.as_str()))
            .enumerate()
        {
            if filtered && !visible.contains(parent.as_str()) {
                omitted += 1;
                continue;
            }
            let target = lanes
                .iter()
                .position(|l| l.as_ref().is_some_and(|l| &l.sha == parent));
            let (target, edge_color) = if let Some(target) = target {
                (target, lanes[target].as_ref().unwrap().color)
            } else {
                let target = if p == 0 && lanes[lane].is_none() {
                    lane
                } else {
                    vacant(&mut lanes)
                };
                let edge_color = if p == 0 {
                    color
                } else {
                    let c = next_color;
                    next_color += 1;
                    c
                };
                lanes[target] = Some(Lane {
                    sha: parent.clone(),
                    color: edge_color,
                });
                (target, edge_color)
            };
            edges.push(Edge {
                from: lane,
                to: target,
                color: edge_color,
                incoming: false,
                continuation: false,
            });
        }
        for (i, pending) in lanes.iter().enumerate() {
            if i != lane
                && edges.iter().any(|e| e.incoming && e.from == i)
                && let Some(pending) = pending
            {
                edges.push(Edge {
                    from: i,
                    to: i,
                    color: pending.color,
                    incoming: false,
                    continuation: true,
                });
            }
        }
        let columns = edges
            .iter()
            .map(|e| e.from.max(e.to) + 1)
            .max()
            .unwrap_or(lane + 1);
        rows.push(Row {
            lane,
            color,
            edges,
            columns,
            omitted,
        });
        while lanes.last().is_some_and(Option::is_none) {
            lanes.pop();
        }
    }
    rows
}
fn vacant(lanes: &mut Vec<Option<Lane>>) -> usize {
    if let Some(i) = lanes.iter().position(Option::is_none) {
        i
    } else {
        lanes.push(None);
        lanes.len() - 1
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    fn c(sha: &str, parents: &[&str]) -> Commit {
        Commit {
            sha: sha.into(),
            parents: parents.iter().map(|p| (*p).into()).collect(),
            subject: String::new(),
            author: String::new(),
            date: String::new(),
            references: String::new(),
        }
    }
    #[test]
    fn merge_edges_join_the_correct_parent_and_pages_preserve_geometry() {
        let commits = vec![
            c("merge", &["main", "side"]),
            c("side", &["root"]),
            c("main", &["root"]),
            c("root", &[]),
        ];
        let rows = layout(&commits, false);
        assert_eq!(layout(&commits[..2], false), rows[..2]);
        assert_eq!(
            rows[0]
                .edges
                .iter()
                .filter(|e| !e.incoming && !e.continuation)
                .count(),
            2
        );
        assert_eq!(rows[1].lane, 1);
        assert_eq!(rows[2].lane, 0);
        assert_eq!(rows[3].lane, 1);
        assert!(
            rows[2]
                .edges
                .iter()
                .any(|e| !e.incoming && e.from == 0 && e.to == 1)
        );
        assert!(!rows[3].edges.iter().any(|e| !e.incoming));
        assert_ne!(rows[0].color, rows[1].color);
        assert_eq!(rows[1].color, rows[3].color);
    }
    #[test]
    fn octopus_roots_duplicates_and_filtered_ancestors_are_explicit() {
        let commits = vec![
            c("m", &["a", "b", "c", "c"]),
            c("a", &[]),
            c("b", &[]),
            c("c", &[]),
            c("other", &[]),
        ];
        let rows = layout(&commits, false);
        assert_eq!(rows[0].columns, 3);
        assert_eq!(rows[4].lane, 0);
        let filtered = layout(&[c("m", &["hidden", "shown"]), c("shown", &[])], true);
        assert_eq!(filtered[0].omitted, 1);
        assert_eq!(filtered[1].lane, 0);
        assert_eq!(layout(&[], false), vec![]);
    }
}
