# git_graph_data.py


class CommitNode:
    def __init__(self, sha: str, message: str, author_name: str, author_email: str, author_date: str):
        self.sha: str = sha
        self.parents: list[str] = []
        self.children: list[str] = []  # To be populated later
        self.message: str = message
        self.author_name: str = author_name
        self.author_email: str = author_email
        self.author_date: str = author_date
        self.references: list[str] = []  # e.g., ['HEAD -> main', 'origin/main', 'refs/tags/v1.0']
        self.is_on_mainline: bool = False  # New attribute
        self.branch_color_idx: int | None = None

        # Layout-related attributes, to be filled by the layout algorithm
        self.x: float = 0.0
        self.y: float = 0.0
        self.column: int = 0
        self.color_idx: int = 0  # For assigning branch colors

    def __repr__(self) -> str:
        return (
            f"CommitNode(sha='{self.sha[:7]}', "
            f"parents={[p[:7] for p in self.parents]}, "
            f"children={[c[:7] for c in self.children]}, "
            f"references={self.references}, "
            f"message='{self.message[:20]}...', "
            f"mainline={self.is_on_mainline}, "
            f"column={self.column}, y={self.y}, "
            f"color_idx={self.color_idx}, "
            f"branch_color_idx={self.branch_color_idx})"
        )


if __name__ == "__main__":
    # Example Usage (optional, for testing the data structure)
    node1 = CommitNode("a1b2c3d4e5f6", "Initial commit", "Jules Verne", "jules@example.com", "2023-01-01")
    node2 = CommitNode("f6e5d4c3b2a1", "Add feature X", "Jules Verne", "jules@example.com", "2023-01-02")
    node3 = CommitNode("abcdef123456", "Merge branch 'dev'", "Jules Verne", "jules@example.com", "2023-01-03")

    node1.children.append(node2.sha)
    node2.parents.append(node1.sha)

    node1.children.append(node3.sha)  # Incorrect, just for example structure
    node3.parents.append(node1.sha)
    node2.children.append(node3.sha)
    node3.parents.append(node2.sha)

    node1.references.append("refs/tags/v0.1")
    node2.references.append("dev")
    node3.references.append("HEAD -> main")
    node3.references.append("origin/main")

    print(node1)
    print(node2)
    print(node3)
