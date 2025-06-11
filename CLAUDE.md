# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview
This repository is a Python-based Git repository management tool, providing a graphical interface to simplify Git operations. It is built using Python and PyQt6.

## Key Commands

### Setup and Installation
1. Clone the repository:
    ```bash
    git clone https://github.com/wynemo/mygit.git
    cd mygit
    ```

2. Create and activate a virtual environment:
    no need, uv will create a virtual environment for you

3. Install dependencies:
    ```bash
    uv sync
    ```

### Running the Application
To run the main program:
```bash
uv run main.py
```

### Testing
Tests are located within the `tests/` directory. Execute tests using:
```bash
bash check.sh
```

## Project Structure
- `dialogs/`: Contains components for various dialog windows.
- `editors/`: Houses text editor-related components.
- `icons/`: Includes SVG and PNG icon resources.
- `tests/`: Consists of unit tests and testing data files.
- `utils/`: Provides helper functions and scripts.