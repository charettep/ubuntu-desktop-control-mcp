# MCP Prompt Library

Prompts in this folder follow the Model Context Protocol prompt shape (mirrors `mcp.types.Prompt` and `mcp.types.GetPromptResult`). Each `*.json` file includes:
- `name`, `title`, `description`
- `arguments`: list of `{ "name", "description", "required" }`
- `messages`: ordered chat turns where `role` is `user` or `assistant` and `content` is a single text block `{ "type": "text", "text": "..." }`

Placeholders use `{{variable}}` so MCP-aware clients can substitute arguments when loading the prompt. All prompts target the ubuntu-desktop-control tools (screenshots, clicks, movement, scaling diagnostics) and favor safe, scaling-aware interactions.
