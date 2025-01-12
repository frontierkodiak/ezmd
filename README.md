# ezmd

ezmd is an **Easy Markdown** tool for converting documents to Markdown using 
[MarkItDown](https://github.com/microsoft/markitdown). 

## Features

- Converts from local files (PDF, docx, images, etc.) or URLs.
- (Optional) LLM-based image descriptions (OpenAI or Google Gemini).
- TUI-based interactive setup and usage.
- Automatic collision handling with `_v2`, `_v3` naming if overwrite is disallowed.
- WSL2 local path support for Windows paths.

## Installation

1. Ensure you have [uv](https://github.com/astral-sh/uv) installed and available.
2. Clone or download this project.
3. `cd` into the project and run:
   ```bash
   uv tool install .
   uv tool update-shell
   ```
4. You can now invoke `ezmd` from the shell.

## Usage

1. **First Run**  
   - If no configuration file exists at `~/.config/ezmd/config.json`, you'll see a first-time setup wizard.
   - Provide base paths, toggle providers, and optionally paste your LLM keys.

2. **Converting a Document**  
   - Run `ezmd` and select "1) Convert a Document".
   - Provide a title and the source (URL or local path).
   - If you have LLM usage enabled, pick which LLM provider (OpenAI or Google).
   - A spinner is displayed, and upon completion, the `.md` file is saved in `~/context/`.

3. **Configuration**  
   - At any time, select "2) Configuration" from the main menu.
   - Change default options, toggle providers, set or clear LLM keys, etc.

4. **Exit**  
   - Choose "3) Exit".

## WSL2 Path Handling

If you’re using Windows paths in WSL2 (e.g., `C:\Users\front\Zotero\paper.pdf`), 
ezmd automatically converts them to `/mnt/c/Users/front/Zotero/paper.pdf`.

## LLM Integration

- **OpenAI**: We store the key in the environment variable `EZMD_OPENAI_KEY`. 
  MarkItDown uses the standard OpenAI API calls for image or PDF embedding usage.
- **Google Gemini**: Some partial support is included, but might need additional 
  code changes if MarkItDown isn't fully compatible with google-genai.

## Development

- You can develop and debug with VSCode by opening the folder in the uv environment, 
  or by editing code directly. You can run `uv run python -m ezmd.main` or `uv run python -m debugpy --listen 5678 -m ezmd.main` for debugging.

## License

This project is licensed under the MIT License.