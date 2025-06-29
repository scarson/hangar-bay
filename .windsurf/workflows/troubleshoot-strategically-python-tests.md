---
description: Review changes, design guides, think big picture, research, best practices check, weigh options
---

I want to be careful we don't get into a loop of regressions from narrowly focused tactical troubleshooting while losing the bigger picture. Before you make any more changes, I want you to "step back" and:
1. Review ALL troubleshooting steps and changes and relevant files (in full - use the view_file tool with #L1-200 to get the full contents), including ideally your prior changes from diffs
2. Review design\fastapi\guides\09-testing-strategies.md for guidance, but remember this is not *the* only source of truth for effective testing
3. Think about the big picture Python test setup and all its components
4. Do some research on fastapi and python test best practices that would be relevant to the project
5. Strategically think about if the current test structures are aligned with best practices
6. Think about potential structural and other improvements. Consider multiple options from different perspectives, as it's a broad problem. 
7. Tell me what you think is best, and justify why you think it / they would be effective or not. What could Cascade to to increase test implementation quality? There may be more than one effective change to implement. There may also be none, if our tests are already well aligned.