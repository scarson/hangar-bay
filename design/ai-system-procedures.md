# AI System Procedures for Hangar Bay

<!-- AI_DOCUMENT_PURPOSE_START -->
<!-- This document serves as a central, human-readable repository for documenting significant, recurring procedures, protocols, or operational patterns designed for AI coding assistants (like Cascade) to execute or participate in within the Hangar Bay project. It aims to capture the "what, why, and how" of these procedures. While AI assistants may be directed to reference specific procedures herein for context or clarification, the primary operational triggers and detailed execution logic for AI are typically stored in associated Cascade Memories. This document is primarily a design record and a guide for human understanding, maintenance, and replication of these AI-involved processes. -->
<!-- AI_DOCUMENT_PURPOSE_END -->

## [AISP-000] AISP Entry Template

<!-- 
This template provides the standard structure and guidance for documenting new AI System Procedures (AISPs). 
When creating a new AISP entry:
1. Copy this entire template section (from "## [AISP-000]..." down to the horizontal rule before the next AISP).
2. Assign a new, unique, sequential AISP-XXX ID (e.g., if the last entry was AISP-001, the new one is AISP-002).
3. Replace "[AISP-000]" in the title and "AISP-XXX" in Section 1 with the new ID.
4. Fill in each section according to the guidance provided in the HTML comments and replace placeholder text.
5. This template itself (AISP-000) should remain in the document for future use.
-->

### 1. Procedure ID
<!-- (Provide the unique, sequential identifier for this procedure, e.g., AISP-00X.) -->
AISP-XXX

### 2. Problem Addressed
<!-- 
Clearly describe:
- The specific issue, challenge, or operational need this procedure is designed to solve.
- What pain point(s) it alleviates.
- Why this procedure is necessary for the project or workflow.
-->
[Placeholder: Describe the problem this procedure addresses.]

### 3. Rationale & Design Philosophy
<!-- 
Explain the core reasoning behind the chosen approach for this procedure:
- What are the key principles guiding its design (e.g., AI-assisted with human supervision, fully automated, event-driven, data-centric)?
- Briefly mention any significant alternative approaches considered and provide a concise justification for why the chosen approach was selected over them.
- This section details the 'why' and 'how' of the procedure's *design and structure*.
-->
[Placeholder: Explain the design rationale and guiding philosophy for this procedure.]

### 4. Trigger Conditions
<!-- 
Specify the exact events, conditions, or tool call outcomes that should prompt an AI assistant (like Cascade) to consider or initiate this procedure. Be precise about:
- Relevant file paths or patterns (e.g., `design/features/F[0-9]{3}-*.md`).
- Specific tool outputs or states.
- User actions or requests.
- Any pre-conditions that must be met.
-->
[Placeholder: Detail the specific trigger conditions for initiating this procedure.]

### 5. Detailed Steps for AI Execution
<!-- 
Provide a clear, numbered, step-by-step description of the actions the AI assistant is expected to perform. Be explicit about:
- Key decisions the AI needs to make at each step.
- Specific tools to be used (e.g., `view_file`, `find_by_name`, `replace_file_content`, `create_memory`, `run_command`). Include example parameters if helpful.
- Information to be extracted, processed, or generated.
- Interactions with the user (e.g., "Propose X to the USER," "Ask the USER for confirmation of Y," "Inform the USER of Z").
- The logical sequence of operations and any conditional branching.
Aim for sufficient detail for an AI to understand the intended logic and flow, but avoid over-scripting every minor internal thought process. Focus on observable actions, critical logic, and key decision points.
-->
1.  [Placeholder: Step 1 description - e.g., "Read file X using `view_file` to extract Y."]
2.  [Placeholder: Step 2 description - e.g., "If Y meets condition Z, then proceed to step A, else proceed to step B."]
3.  ...

### 6. Expected Outcome / Success Criteria
<!-- 
Describe the desired state of the system, project artifacts, or information after the procedure has been successfully completed. 
- What are the tangible results or outputs?
- How can the success of this procedure be measured or verified?
- What specific positive impact does this procedure aim to achieve? (This can inform the 'Rationale' section of an operational AI memory for this procedure).
This section defines 'what good looks like' post-execution and clarifies the procedure's direct benefits.
-->
[Placeholder: Describe the expected outcomes, success criteria, and benefits of this procedure.]

### 7. Supporting Implementation Details
<!-- 
List key resources, configurations, or related information relevant to this procedure's implementation and execution by an AI.
- **Associated Cascade Memories:** (If this AISP is intended to be backed by an AI memory, list the Memory ID here once created, or note if a new one should be created. E.g., "Primary operational logic is stored in Cascade Memory ID: YYYY-YYYY" or "A Cascade Memory should be created to operationalize this AISP.")
- **Key Tools Involved:** (List the primary tools the AI will use, e.g., `view_file`, `replace_file_content`, `codebase_search`.)
- **Relevant Configuration Files/Paths:** (If applicable, list any specific configuration files or critical system paths the AI needs to be aware of for this procedure.)
- **Cross-references:** (Links to other relevant AISPs, design documents, or specifications.)
-->
*   **Associated Cascade Memories:** [Placeholder or N/A]
*   **Key Tools Involved:** [Placeholder: List tools]
*   **Relevant Configuration Files/Paths:** [Placeholder or N/A]
*   **Cross-references:** [Placeholder or N/A]

### 8. Notes for Human Reviewers & Maintainers
<!-- 
Provide any additional context, advice, or considerations for human developers or project maintainers who are reviewing, overseeing, evolving, or manually executing this procedure. Highlight:
- Potential edge cases, common pitfalls, or complexities to be aware of.
- Areas requiring careful human oversight, judgment, or manual intervention.
- Guidance on how this AISP entry relates to operational AI memories: For instance, when encoding this procedure into an AI's memory, the memory's "Rationale" section should ideally focus on the benefits/outcomes (drawing from this AISP's "Expected Outcome / Success Criteria" section), as this AISP document already covers the detailed *design rationale* (in Section 3).
- Suggestions for future improvements or evolution of this procedure.
-->
[Placeholder: Add any notes, caveats, or guidance for human reviewers and maintainers.]

### 9. Version & Last Updated
<!-- 
Track the version and update history of this specific AISP entry.
- **Version:** (e.g., 1.0, 1.1) - Increment for significant changes.
- **Last Updated:** (Date of the last modification, e.g., YYYY-MM-DD)
-->
*   **Version:** 1.0
*   **Last Updated:** [YYYY-MM-DD]

---

---

## [AISP-001] Automated Maintenance of `feature-index.md`

### 1. Procedure ID

AISP-001

### 2. Problem Addressed

As the Hangar Bay project grows, the number of feature specification documents (e.g., `F001-*.md`, `F002-*.md`) increases. Manually keeping the central `design/features/feature-index.md` file accurate and up-to-date with titles, statuses, descriptions, and paths for all features becomes error-prone and inefficient. An outdated or incorrect index can hinder both human developers and AI assistants in locating the correct feature specifications, potentially leading to wasted effort or work based on incorrect information.

### 3. Rationale & Design Philosophy

This procedure aims to semi-automate the maintenance of `feature-index.md` to ensure its accuracy and reliability.

*   **Design Principles:**
    *   **AI-Assisted, Human-Supervised:** Leverage the AI's ability to detect file changes and extract information, but retain human oversight and approval for final modifications to the index. This balances automation benefits with the need for correctness in critical project documentation.
    *   **Trigger-Based:** The procedure is initiated by specific events (creation/modification of feature spec files), making it event-driven rather than requiring constant polling or manual invocation.
    *   **Data-Driven:** Relies on extracting metadata directly from the source feature specification files and the existing index.
    *   **Clarity & Explicitness:** The AI should clearly propose changes to the user, explaining what is being added/modified and why.
*   **Alternatives Considered:**
    *   *Fully Manual Updates:* Prone to errors, omissions, and becoming outdated.
    *   *Fully Automated Updates (No Human Review):* Risks introducing errors into the index if the AI misinterprets a change or if a feature spec is in a transient, incomplete state.

### 4. Trigger Conditions

This procedure should be considered by the AI assistant (Cascade) after any successful `write_to_file` (indicating new feature spec creation) or `replace_file_content` (indicating existing feature spec modification) tool call that targets a file meeting the following criteria:
*   Located within the `c:\Users\Sam\OneDrive\Documents\Code\hangar-bay\design\features\` directory.
*   Filename matches the pattern `F[0-9]{3}-*.md`.

### 5. Detailed Steps for AI Execution

1.  **Acknowledge Trigger:** Note that a relevant feature specification file has been created or modified.
2.  **Read `feature-index.md`:** Use the `view_file` tool to get the current content of `c:\Users\Sam\OneDrive\Documents\Code\hangar-bay\design\features\feature-index.md`.
3.  **List Feature Files:** Use the `find_by_name` tool to get a list of all files in `c:\Users\Sam\OneDrive\Documents\Code\hangar-bay\design\features\` matching the pattern `F[0-9]{3}-*.md`.
4.  **Gather Metadata from Feature Specs:** For each feature file identified (especially focusing on the one(s) that triggered the procedure, but also verifying others for consistency if deemed efficient):
    a.  **Feature ID:** Extract from the filename (e.g., `F00X` from `F00X-SomeName.md`).
    b.  **Title:** Use `view_file` to read the feature spec. Extract the primary title (typically the content of the first H1 heading, e.g., `# Feature Title`).
    c.  **Status:** Attempt to determine the feature's status. Look for frontmatter (e.g., `status: Draft`) or a dedicated "Status" section. If not found, use 'To be determined' as a placeholder or explicitly ask the USER for the status.
    d.  **Description:** Attempt to extract a brief description (1-2 sentences). Look for an "Overview," "Summary," or the initial paragraph(s) after the title. If a concise summary isn't obvious, use a placeholder (e.g., "Refer to document.") or ask the USER to provide one.
    e.  **Relative Path:** Construct the relative path from the `design/features/` directory (e.g., `./F00X-SomeName.md`).
5.  **Compare and Identify Changes:** Compare the gathered metadata for all feature files with the existing entries in `feature-index.md`.
    *   Identify new features not yet in the index.
    *   Identify existing features in the index whose Title, Status, Description, or Path might have changed based on the latest spec file content.
6.  **Propose Updates to USER:** Present a clear summary of proposed changes to `feature-index.md`.
    *   For new entries, show the full proposed markdown line.
    *   For modifications, clearly show the old line and the new proposed line, highlighting the change.
    *   Explain the reason for each proposed change (e.g., "New feature spec created," "Title updated in F00X.md").
7.  **Await USER Approval:** Do not proceed with changes without explicit user confirmation.
8.  **Apply Approved Changes:** If the USER approves, use the `replace_file_content` tool to apply the exact, confirmed changes to `feature-index.md`. This typically involves replacing existing lines or adding new lines in the table section of the index file.

### 6. Expected Outcome / Success Criteria

*   The `design/features/feature-index.md` file accurately reflects the current set of feature specifications in the `design/features/` directory, including their correct Feature ID, Title, Status, Description, and Relative Path.
*   The user has been informed of the changes and has approved them.

### 7. Supporting Implementation Details

*   **Associated Cascade Memories:**
    *   `8ab3f7a9-9f10-42c1-a282-b8ad6eefe5b6` (Primary memory defining this operational procedure for Cascade).
    *   `894cb924-09d3-4293-b3d6-45d441d83616` (Memory about the existence and purpose of `feature-index.md`).
*   **Key Tools Involved:**
    *   `view_file`
    *   `find_by_name`
    *   `replace_file_content`

### 8. Notes for Human Reviewers & Maintainers

*   The AI's ability to perfectly extract "Status" and "Description" might vary based on the consistency of feature spec documents. Human users should be prepared to provide or confirm this information if the AI cannot reliably determine it.
*   Ensure the AI proposes changes in the correct markdown table format expected by `feature-index.md`.
*   This procedure focuses on content updates. Major structural changes to `feature-index.md` itself (e.g., adding new columns to the table) would likely require manual intervention and updates to this procedure's documentation.
*   When encoding this procedure into an AI's operational memory (e.g., a Cascade Memory), consider structuring the memory's "Rationale" or equivalent section to primarily emphasize the *benefits and expected outcomes* of the procedure. This can be drawn from this AISP's "Expected Outcome / Success Criteria" section. The AISP document itself already details the *design rationale* of the procedure in its dedicated section. This distinction helps ensure the AI's operational memory clearly links its actions to their intended positive impact.

### 9. Version & Last Updated

*   **Version:** 1.0
*   **Last Updated:** 2025-06-06

---
