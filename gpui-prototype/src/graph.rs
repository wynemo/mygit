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
impl Edge {
    /// Horizontal lane position at the boundary between virtual rows. Both
    /// halves interpolate between the same two row-center endpoints.
    pub fn boundary_lane(&self, adjacent: Option<&Row>) -> f32 {
        let matching = adjacent.and_then(|row| {
            row.edges.iter().find(|edge| {
                edge.incoming != self.incoming
                    && edge.color == self.color
                    && if self.incoming {
                        edge.to == self.from
                    } else {
                        edge.from == self.to
                    }
            })
        });
        if self.incoming {
            (matching.map_or(self.from, |edge| edge.from) as f32 + self.to as f32) / 2.
        } else {
            (self.from as f32 + matching.map_or(self.to, |edge| edge.to) as f32) / 2.
        }
    }
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
                    to: if l.sha == commit.sha { lane } else { i },
                    color: l.color,
                    incoming: true,
                    continuation: l.sha != commit.sha,
                })
            })
            .collect();
        // Multiple branches may await the same ancestor. Join them at its node,
        // retaining the leftmost lane and its color for the shared history.
        for pending in &mut lanes {
            if pending.as_ref().is_some_and(|l| l.sha == commit.sha) {
                *pending = None;
            }
        }
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
            // Keep each first-parent lane until the ancestor row itself. Joining
            // an already pending parent here changes the side branch's color and
            // bends its line into the main lane above the ancestor node.
            let (target, edge_color) = if let Some(target) = target
                && !(p == 0 && target != lane)
            {
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
                // A lane consumed at this node may already have been reused by
                // another parent. Only an incoming through-line needs a lower
                // continuation; the new parent has its own outgoing edge.
                && edges.iter().any(|e| e.incoming && e.continuation && e.from == i)
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
        assert_eq!(rows[3].lane, 0);
        assert!(
            rows[3]
                .edges
                .iter()
                .any(|e| e.incoming && e.from == 1 && e.to == 0)
        );
        assert!(!rows[3].edges.iter().any(|e| !e.incoming));
        assert_ne!(rows[0].color, rows[1].color);
        assert_eq!(rows[0].color, rows[3].color);
    }
    #[test]
    fn shared_ancestor_keeps_main_lane_and_side_color_until_the_join() {
        let commits = vec![
            c("merge", &["main1", "side"]),
            c("main1", &["main2"]),
            c("main2", &["main3"]),
            c("main3", &["main4"]),
            c("main4", &["main5"]),
            c("side", &["root"]),
            c("main5", &["root"]),
            c("root", &["older"]),
            c("older", &[]),
        ];
        let rows = layout(&commits, false);
        for end in 1..=commits.len() {
            assert_eq!(layout(&commits[..end], false), rows[..end]);
        }
        assert_eq!(
            rows.iter().map(|r| r.lane).collect::<Vec<_>>(),
            vec![0, 0, 0, 0, 0, 1, 0, 0, 0]
        );
        assert_eq!(rows[0].color, rows[7].color);
        assert!(
            rows[6]
                .edges
                .iter()
                .any(|e| !e.incoming && e.from == 0 && e.to == 0 && e.color == rows[0].color)
        );
        assert!(
            rows[7]
                .edges
                .iter()
                .any(|e| e.incoming && e.from == 1 && e.to == 0 && e.color == rows[5].color)
        );
        assert_eq!(rows[8].columns, 1);
    }
    #[test]
    fn unmerged_side_branch_keeps_its_color_and_joins_at_ancestor_node() {
        let commits = vec![
            c("main", &["root"]),
            c("side-tip", &["side-base"]),
            c("side-base", &["root"]),
            c("root", &["older"]),
            c("older", &[]),
        ];
        let rows = layout(&commits, false);
        assert_eq!(rows[1].lane, 1);
        assert_eq!(rows[2].lane, 1);
        assert_eq!(rows[1].color, rows[2].color);
        assert_ne!(rows[0].color, rows[1].color);
        // The side branch leaves its last node vertically, in its own color.
        assert!(rows[2].edges.iter().any(|e| !e.incoming
            && !e.continuation
            && e.from == 1
            && e.to == 1
            && e.color == rows[1].color));
        // Its incoming half reaches the ancestor node, not the mainline boundary.
        assert!(rows[3].edges.iter().any(|e| e.incoming
            && !e.continuation
            && e.from == 1
            && e.to == rows[3].lane
            && e.color == rows[1].color));
        assert_eq!(rows[3].color, rows[0].color);
        assert_eq!(rows[4].columns, 1);
        for end in 1..=commits.len() {
            assert_eq!(layout(&commits[..end], false), rows[..end]);
        }
    }

    #[test]
    fn bends_span_row_centers_and_virtual_row_boundaries_match() {
        let rows = layout(
            &[
                c("merge", &["main", "side"]),
                c("side", &["root"]),
                c("main", &["root"]),
                c("root", &[]),
            ],
            false,
        );
        for pair in rows.windows(2) {
            for outgoing in pair[0].edges.iter().filter(|e| !e.incoming) {
                let incoming = pair[1]
                    .edges
                    .iter()
                    .find(|e| e.incoming && e.from == outgoing.to && e.color == outgoing.color)
                    .unwrap();
                let boundary = (outgoing.from as f32 + incoming.to as f32) / 2.;
                assert_eq!(outgoing.boundary_lane(Some(&pair[1])), boundary);
                assert_eq!(incoming.boundary_lane(Some(&pair[0])), boundary);
            }
        }
        let fork = rows[0]
            .edges
            .iter()
            .find(|e| !e.incoming && e.to == 1)
            .unwrap();
        assert_eq!(fork.boundary_lane(Some(&rows[1])), 0.5);
        let join = rows[3]
            .edges
            .iter()
            .find(|e| e.incoming && e.from == 1)
            .unwrap();
        assert_eq!(join.boundary_lane(Some(&rows[2])), 0.5);
    }

    #[test]
    fn joined_lane_reused_by_a_merge_parent_has_no_extra_vertical_segment() {
        let commits = vec![
            c("first-merge", &["main", "yellow"]),
            c("yellow", &["second-merge"]),
            c("main", &["second-merge"]),
            c("second-merge", &["older-main", "red"]),
            c("red", &["root"]),
            c("older-main", &["root"]),
            c("root", &[]),
        ];
        let rows = layout(&commits, false);
        let join = &rows[3];
        assert!(
            join.edges
                .iter()
                .any(|e| e.incoming && e.from == 1 && e.to == 0)
        );
        assert!(
            join.edges
                .iter()
                .any(|e| !e.incoming && e.from == 0 && e.to == 1)
        );
        assert!(!join.edges.iter().any(|e| !e.incoming && e.from == 1));
        assert_eq!(join.edges.iter().filter(|e| !e.incoming).count(), 2);
        let red = &rows[4];
        let outgoing = join
            .edges
            .iter()
            .find(|e| !e.incoming && e.to == red.lane)
            .unwrap();
        assert_eq!(outgoing.color, red.color);
        for end in 1..=commits.len() {
            assert_eq!(layout(&commits[..end], false), rows[..end]);
        }
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
