set -e
ruff check --select I --exclude git-cola/ --exclude tests/
ruff format . --exclude git-cola/ --exclude tests/

# check if is linux
if [ "$(uname)" == "Linux" ]; then
    xvfb-run uv run python -m unittest discover -s tests
else
    uv run python -m unittest discover -s tests
fi
