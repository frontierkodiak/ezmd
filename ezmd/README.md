# ezmd

ezmd is an **Easy Markdown** tool for converting documents to Markdown using 
[MarkItDown](https://github.com/microsoft/markitdown). 

## Features

- Converts from local files (PDF, docx, images, etc.) or URLs.
- (Optional) LLM-based image descriptions (OpenAI only).
- If Google Gemini is selected, MarkItDown is *not* called with the Gemini LLM; 
  instead, ezmd does a *custom* post-processing step, appended to the final Markdown.
- Automatic collision handling: if a file exists, ezmd prompts for a new version 
  or a custom filename, letting you cancel if needed.
- WSL2 path support for Windows paths.

## Installation

1. Ensure you have [uv](https://github.com/astral-sh/uv) installed.
2. Clone or download this project.
3. `cd` into the project and run:
   ```bash
   uv tool install .
   uv tool update-shell
   ```
4. You can now invoke `ezmd` from the shell.

## Environment Variables in `.env`

ezmd stores your API keys in `~/.config/ezmd/ezmd.env`.  
Each time you run the tool, the environment is reloaded, so 
your keys persist across new shells in the uv environment.

For example:
```
EZMD_OPENAI_KEY=sk-...
EZMD_GOOGLE_GEMINI_KEY=AIza...
```

## Usage

1. **First Run**  
   - If no configuration file exists (`~/.config/ezmd/config.json`), 
     you'll see a setup wizard. Provide base paths, toggle providers, 
     and optionally paste your LLM keys.

2. **Converting a Document**  
   - Run `ezmd` -> "1) Convert a Document".
   - Provide a title and the source (URL or local path).
   - Choose an LLM provider (OpenAI or Google Gemini). 
     - If OpenAI, MarkItDown uses OpenAI for image analysis. 
     - If Google Gemini, we skip MarkItDown’s built-in approach and do a custom `_do_gemini_processing` step appended at the end.
   - If collisions occur, ezmd prompts for a new name or `c` to cancel.
   - The `.md` file is saved in `~/context/` by default.

3. **Configuration**  
   - "2) Configuration" from the main menu lets you 
     adjust paths, default providers, etc.

4. **Exit**  
   - Choose "3) Exit".

## Development

- You can develop and debug with VSCode or directly using:
  ```bash
  uv run python -m ezmd.main
  ```
- Logs appear in stdout.  
- The environment variables are stored in `.env` at `~/.config/ezmd/ezmd.env`.

## License

This project is licensed under the MIT License. 