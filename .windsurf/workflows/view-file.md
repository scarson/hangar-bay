---
description: Reads the full contents of a file, handling potentially long files.
---
When instructed to read a file, you must follow this protocol to ensure you retrieve the complete content:

1.  Make an initial call to the `view_file` tool with a large range, typically `StartLine: 1` and `EndLine: 400`.
2.  Carefully examine the tool's output. Pay attention to any summary information that indicates more lines exist beyond the range you requested.
3.  If you have any reason to believe the file is longer than 400 lines, you MUST proactively make subsequent `view_file` calls (e.g., `StartLine: 401`, `EndLine: 800`) until you are confident you have read the entire file.
4.  This is a critical step to ensure you have full context before making decisions or edits. Do not assume a file is short.
