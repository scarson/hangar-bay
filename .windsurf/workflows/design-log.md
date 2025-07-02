---
description: Add new design log entry/entries
---

Think about the important design decisions we've made recent. Append one or more design\meta\design-log.md entries to cover them with a level of detail that's useful to humans and Cascade. Note: The design-log.md file is well over 1,000 lines long. Do NOT try to retrive its content starting from the beginning or you won't find the end of the file and will unintentionally place the new entry or entries in the middle of the log. Use footer "DESIGN_LOG_FOOTER_MARKER_V1 :: (End of Design Log. New entries are appended above this line. Entry heading timestamp format: YYYY-MM-DD HH:MM:SS-05:00 (e.g., 2025-06-06 09:16:09-05:00))" to target your update. Run this PowerShell command from the project root (C:\Users\Sam\OneDrive\Documents\Code\hangar-bay) to get the line count if necessary:
"(Get-Content design\meta\design-log.md).Count"

Each entry should end with:

---