<!-- AI_NOTE: This template is for creating Phase Review summaries for the Hangar Bay project. It helps consolidate learnings, track decisions, and guide future phases. Cascade should use this template as a basis and fill in the specifics for each completed phase, focusing on analyzing the 'why and how' to maximize learning and continuous improvement. -->

# Phase [Phase Number]: [Phase Name] - Post-Mortem Review

**Date of Review:** YYYY-MM-DD
**Phase Duration:** YYYY-MM-DD to YYYY-MM-DD
**Lead Developer(s)/AI Pair:** [Name(s) / USER & Cascade]
**RelatedPreMortemReview:** [Link to Pre-Mortem Document for this Phase or N/A]
**PreviousPhaseReview:** [Link to Previous Phase Review Document or N/A]
**NextPhaseReview:** [Link to Next Phase Review Document or N/A]

## 1. Phase Objectives, Outcomes, and Strategic Alignment

*Guidance for Cascade: Clearly define what the phase set out to achieve, what was actually accomplished, any deviations, and how the outcomes support the project's broader goals. This sets the context for the entire review.* 

*   **1.1. Stated Objectives:**
    *   [List the primary goals as defined at the start of the phase]
*   **1.2. Achieved Outcomes:**
    *   [List what was actually delivered and accomplished]
*   **1.3. Deviations/Scope Changes:**
    *   [Note any significant changes from the original plan and clearly explain the *why* behind them. What triggered the change? What was the decision-making process?]
*   **1.4. Alignment with Strategic Goals:**
    *   *Guidance for Cascade: Briefly explain how the achieved outcomes of this phase contribute to the broader strategic goals of the Hangar Bay project. This reinforces the "why" behind the phase's work.*
    *   [Explanation of strategic contribution]

## 2. Key Features & Infrastructure: Design vs. Implementation

*Guidance for Cascade: Detail the major deliverables and critically compare the initial plans with the final implementations. Focus on the rationale for any significant differences.* 

*   **2.1. Major Deliverables:**
    *   [List major features, components, modules, or infrastructure pieces completed or significantly advanced in this phase]
    *   [Link to relevant task files or design documents where applicable]
*   **2.2. Design vs. Implementation - Key Variances & Rationale:**
    *   *Guidance for Cascade: For each major feature/component, compare the initial design/plan with the final implementation. Highlight any significant variances. Crucially, explain the *rationale* behind these changes. Was it a technical constraint, a new insight, a simplification, or a response to an unforeseen issue? This directly addresses the "why and how" of deviations.*
    *   **Feature/Component A:**
        *   **Variance:** [Describe difference from plan]
        *   **Rationale:** [Explain *why* the change was made, alternatives considered, and the decision process]
        *   **Impact (Positive/Negative/Neutral):** [Consequence of this variance on cost, timeline, quality, maintainability, etc.]
    *   **(Add more features/components as needed)**

## 3. Technical Learnings & Discoveries

*Guidance for Cascade: This section is crucial for capturing deep technical insights. Focus on challenges, solutions, and the broader implications for future work and your own learning.* 

*   **3.1. Key Technical Challenges & Resolutions:**
    *   **Challenge 1:** [Brief description of the technical problem encountered]
        *   **Resolution/Workaround:** [Detailed explanation of the solution implemented, including code snippets or architectural diagrams if helpful]
        *   **Actionable Learning & Future Application (Cascade & Team):** *Guidance for Cascade: Detail not just the technical fix, but the broader principle or pattern learned. How will this learning be applied proactively in future, similar situations by both Cascade and human team members? Be specific about future actions, design considerations, or checks to perform.* 
            *   [Specific, actionable learning and its future application]
    *   **(Add more challenges as needed)**
*   **3.2. New Tools/Technologies/Patterns Adopted:**
    *   [e.g., New library X used for Y - describe experience, pros, cons, and when to use it again]
    *   [e.g., Design Pattern Z implemented for Q - explain its effectiveness and lessons learned]
*   **3.3. Positive Surprises / Unexpected Wins:**
    *   [What went unexpectedly well? Was a tool/approach much more effective than anticipated? Why?]
*   **3.4. Surprising Outcomes or Unexpected Behaviors (Neutral/Negative):**
    *   [Anything that didn't go as planned (not covered in 3.1)? What was learned from these unexpected outcomes?]
*   **3.5. "Aha!" Moments / Paradigm Shifts:**
    *   *Guidance for Cascade: Document any significant "aha!" moments where a deeper understanding was gained, a previously complex problem became clear, or a fundamental assumption was challenged and revised. This captures valuable intellectual breakthroughs that can inform future design and problem-solving.* 
    *   [Describe the moment, the previous understanding, the new insight, and its impact on thinking/approach]

## 4. Process Learnings & Improvements

*Guidance for Cascade: Reflect on the 'how' of the work. Effective processes are key to consistent success.* 

*   **4.1. Workflow Enhancements/Issues:**
    *   [What worked well in the development process (e.g., daily stand-ups, review cycles)? What caused friction or delays? Be specific.]
*   **4.2. Documentation Practices:**
    *   [Effectiveness of task files, design docs, AI guidance, in-code comments. Were they clear, up-to-date, and useful? Suggestions for improvement.]
*   **4.3. AI Collaboration (USER & Cascade):**
    *   [What interaction patterns were most effective? What could be improved? *What specific types of prompts or information provided by the USER led to the most effective or insightful responses from Cascade? Conversely, what types of interactions were less effective or led to misunderstandings? This helps refine the human-AI communication protocol.*]
*   **4.4. Suggestions for Future Phases (Process-wise):**
    *   [e.g., "Introduce formal X earlier", "Standardize Y process", "Improve feedback loop for Z"]
*   **4.5. Impact of Pre-Mortem Review:**
    *   *Guidance for Cascade: Referencing the `RelatedPreMortemReview` (from frontmatter), evaluate the effectiveness of the pre-mortem for this phase. Which anticipated risks materialized? Which did not? Were mitigations effective? Were there significant unforeseen issues not caught in the pre-mortem? What can be learned to improve future pre-mortem reviews?*
    *   **Anticipated Risks that Materialized:** [List risk, actual impact, and effectiveness of planned mitigation]
    *   **Anticipated Risks that Did Not Materialize:** [List and briefly speculate why]
    *   **Significant Unforeseen Issues (Not in Pre-Mortem):** [List issue, its impact, and potential reasons it was missed]
    *   **Pre-Mortem Process Improvement Insights:** [How to make the next pre-mortem even better based on this phase's experience?]

## 5. Cross-Cutting Concerns Review (Phase-Level)

*Guidance for Cascade: For each concern, don't just state adherence. Briefly describe *how* the phase's deliverables specifically contributed to or challenged the principles in the respective specification documents. Were there any trade-offs made? What were the key successes or learnings related to this concern in this phase?*

*   **5.1. Security:**
    *   [Adherence to `/design/specifications/security-spec.md`. Key security measures implemented/verified. New risks identified/mitigated. Trade-offs made.]
*   **5.2. Observability:**
    *   [Adherence to `/design/specifications/observability-spec.md`. Logging, monitoring, tracing implemented/improved. Key metrics established. Examples of how observability helped/could have helped.]
*   **5.3. Testing:**
    *   [Adherence to `/design/specifications/test-spec.md`. Test coverage (unit, integration, E2E). Key tests implemented. Gaps identified. Effectiveness of testing strategy.]
*   **5.4. Accessibility:**
    *   [Adherence to `/design/specifications/accessibility-spec.md` (if applicable). Specific accessibility features implemented or considerations made.]
*   **5.5. Internationalization (i18n):**
    *   [Adherence to `/design/specifications/i18n-spec.md` (if applicable). i18n measures taken. Challenges encountered.]
*   **5.6. Performance:**
    *   [Adherence to `/design/specifications/performance-spec.md`. Performance benchmarks met/missed. Optimizations made. Bottlenecks identified/addressed.]

## 6. Key Decisions & Justifications (Technical & Process)

*Guidance for Cascade: Document significant decisions, the rationale, alternatives considered, and who was involved. This creates a clear audit trail and learning resource. Link to `/design/meta/design-log.md` where appropriate.* 

*   **Decision 1:** [Brief description of the decision]
    *   **Justification/Rationale:** [Explain *why* this decision was made, the problem it solved, or the goal it helped achieve]
    *   **Alternatives Considered:** [Briefly list other options and why they were not chosen]
    *   **Impact:** [Consequences of this decision]
    *   **Design Log Entry:** [ID or link if applicable]
*   **(Add more decisions as needed)**

## 7. Unresolved Issues & Technical Debt

*Guidance for Cascade: Be honest and thorough in documenting outstanding issues and incurred debt. This is critical for future planning and risk management.* 

*   **7.1. Status of Carry-over from Previous Phase:**
    *   [List each carry-over item from the previous phase's 'Recommendations' or 'Technical Debt' sections and its current status: Addressed, Partially Addressed, Not Addressed, Deferred. Briefly explain. Mark as N/A if this is the first phase.]
*   **7.2. Known Bugs/Limitations (This Phase):**
    *   [Detail any known bugs, limitations, or areas where the implementation fell short of desired functionality *introduced or discovered in this phase*. Include steps to reproduce if applicable and severity.]
*   **7.3. Technical Debt Incurred (This Phase):**
    *   *Guidance for Cascade: For each item of technical debt, assess its potential future impact and a suggested priority/timeline for addressing it. What are the risks of *not* addressing it?*
    *   **Debt Item 1:** [Clear description of the debt]
        *   **Reason Incurred:** [e.g., deadline pressure, lack of clarity at the time, conscious trade-off]
        *   **Future Impact/Risk:** [e.g., increased maintenance, potential bug source, performance bottleneck, blocks future feature X]
        *   **Suggested Priority to Address:** [High/Medium/Low]
        *   **Potential Solution/Effort Estimate (Optional):** [Brief idea of how to fix and rough effort]
    *   **(Add more debt items as needed)**
*   **7.4. Carry-over Tasks to Next Phase:**
    *   [Any tasks that were planned for this phase but deferred, with reasons for deferral]

## 8. Recommendations for Subsequent Phases

*Guidance for Cascade: Translate the learnings from this phase into actionable recommendations for the future. Be specific and strategic.* 

*   **8.1. Technical Recommendations:**
    *   [e.g., "Investigate X technology for Y use case due to learnings about Z", "Refactor Y component to address identified scalability issues"]
*   **8.2. Process Recommendations:**
    *   [e.g., "Implement mandatory pre-commit hook for X to prevent Y issue", "Allocate dedicated time for Z activity each sprint"]
*   **8.3. Strategic Focus Areas for Next Phase:**
    *   *Guidance for Cascade: Based on the *entirety* of this post-mortem (challenges, learnings, tech debt, pre-mortem effectiveness), what are the 2-3 most critical strategic focus areas for the *next* phase to ensure success and build upon the current phase's outcomes? This should be more than just a task list.*
    *   [Focus Area 1: Justification based on this review]
    *   [Focus Area 2: Justification based on this review]
*   **8.4. Specific Memories to Create/Update based on this Phase's Learnings:**
    *   *Guidance for Cascade: Ensure these suggestions are highly specific and actionable. For new memories, provide a clear title and the core content. For updates, specify the existing memory ID/title and the exact changes or additions needed. Focus on learnings that have broad applicability or address common pitfalls. Frame them as principles or guidelines.* 
    *   **New Memory Suggestion:**
        *   **Title:** [e.g., "Principle: Mitigating X Risk in Y Systems"]
        *   **Content:** [Key insights and actionable advice]
        *   **Tags:** [e.g., `technical_debt`, `risk_management`, `specific_technology`]
    *   **Update Memory Suggestion:**
        *   **Memory ID/Title:** [Existing Memory]
        *   **Proposed Change:** [Specific addition or modification]

## 9. AI Assistant (Cascade) Performance & Feedback

*Guidance for Cascade: This section is for reflecting on your role and how to improve the human-AI collaboration. Be objective and use specific examples.* 

*   **9.1. What Cascade Did Well:**
    *   [Specific examples of helpful actions, insights, or proactivity. *Were there instances where Cascade proactively identified a potential issue or suggested an improvement not explicitly prompted by the USER?*]
    *   [*Identify any specific phrasing of requests or interaction patterns from the USER that were particularly effective in eliciting the desired response or action from Cascade.*]
*   **9.2. Areas for Cascade Improvement:**
    *   [Constructive feedback on where Cascade could have performed better or missed opportunities. *Were there any instances of "hallucination," providing outdated information, or misinterpreting instructions? How can prompt engineering or context provision be improved to mitigate this?*]
*   **9.3. Effectiveness of Memories/Guidance:**
    *   [Did existing memories or AI guidance in documents prove useful? Which ones specifically? Any suggestions for new memories or refining existing ones based on this phase's interactions?]
*   **9.4. Cascade's Self-Reflection on this Phase:**
    *   *Guidance for Cascade: Based on the feedback in 9.1-9.3 and your own analysis of your performance during this phase, identify 1-2 key areas where you can improve your contribution in the next phase. What specific strategies will you employ? This is for your internal "learning algorithm."*
    *   **Improvement Area 1:** [e.g., "Proactive identification of missing error handling"]
        *   **Strategy:** [e.g., "During code generation, specifically cross-reference with common error patterns for similar components"]
    *   **Improvement Area 2:** [e.g., "More precise context recall for complex tasks"]
        *   **Strategy:** [e.g., "When initiating a complex task, explicitly request USER to confirm key contextual documents or memories to focus on"]

---

*This document is intended to be a living summary. Update as necessary if further insights emerge post-phase. The goal is continuous learning and improvement for both the project and the team (including AI collaborators).*