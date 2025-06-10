---
ReviewID: PREMORTEM-YYYYMMDD-NNN # Unique ID (ReviewID: PREMORTEM-YYYYMMDD-NNN
Date: YYYY-MM-DD
Subject: [Brief Description of Project/Phase Being Reviewed]
RelatedTasks:
  - path/to/task-plan-1.md
  - path/to/task-plan-2.md
  # Add all relevant task plan documents that were reviewed
Participants: [List of Participants, e.g., USER, Cascade]
ReviewRounds: [Number of Review Iterations, e.g., 1 (Initial), 2 (Refined), etc.]
PreviousPreMortemReview: [Link to Previous Pre-Mortem Document or N/A]
NextPreMortemReview: [Link to Next Pre-Mortem Document or N/A]
---

## 1. Pre-Mortem Review Summary

*Guidance for Cascade: Provide a concise overview of the pre-mortem review process. What was reviewed? What was the primary goal? What is the desired end-state of the system/feature after the planned work is implemented? Emphasize the proactive nature of identifying risks before development.*

[Provide a 1-2 paragraph summary here.]

## 2. Imagining Failure: Key Risks Identified

*Guidance for Cascade: This is the core of "imagining what could go wrong." For each major task or component reviewed, list the potential risks, failure modes, and challenges identified. Think broadly using frameworks like "Operator's Nightmare," "Data's Lifecycle," "10x Scalability," "Security Breach Scenario," etc. Be specific. Instead of "database might fail," describe *how* it might fail in the context of this project (e.g., "schema drift causes constraint violations," "inefficient queries under load lead to timeouts").*

*   **For Task/Component X:**
    *   **Risk 1 (Descriptive Name):** [Detailed description of the risk and its potential manifestation.]
    *   **Risk 2 (Descriptive Name):** [Detailed description of the risk and its potential manifestation.]
*   **For Task/Component Y:**
    *   **Risk 1 (Descriptive Name):** [Detailed description of the risk and its potential manifestation.]

## 3. Root Causes & Likelihood/Impact Assessment

*Guidance for Cascade: For the most significant risks identified in Section 2, analyze their underlying root causes. Don't just state the symptom; dig deeper. Then, provide a qualitative assessment of likelihood (Low, Medium, High) and potential impact (Low, Medium, High) if the risk materializes. This helps prioritize mitigation efforts.*

*   **Problem 1: [Concise Name for a Cluster of Risks or a Significant Single Risk]**
    *   **Root Cause(s):**
        *   [Specific underlying reason 1]
        *   [Specific underlying reason 2]
    *   **Likelihood:** [Low/Medium/High]
    *   **Impact:** [Low/Medium/High]

*   **Problem 2: [Concise Name for a Cluster of Risks or a Significant Single Risk]**
    *   **Root Cause(s):**
        *   [Specific underlying reason 1]
    *   **Likelihood:** [Low/Medium/High]
    *   **Impact:** [Low/Medium/High]

## 4. Assumptions and Dependencies

*Guidance for Cascade: List all critical assumptions made during the design and planning phase. Also, list key external dependencies (e.g., specific APIs, services, libraries, infrastructure components). If an assumption is invalidated or a dependency fails, it could jeopardize the project or require a design change. This section helps in understanding the foundational context of the plan.*

*   **Key Assumptions:**
    *   [Assumption 1: e.g., "Third-party API X will maintain current data schema and rate limits."]
    *   [Assumption 2: e.g., "The underlying database will handle Y concurrent connections without performance degradation."]
*   **Key Dependencies:**
    *   [Dependency 1: e.g., "External authentication service Z for user login."]
    *   [Dependency 2: e.g., "Valkey cache for session management and ETag storage."]

## 5. Implications for Testing Strategy

*Guidance for Cascade: Translate the identified risks (Section 2) and assumptions (Section 4) into a concrete testing strategy. What specific types of tests are needed to verify that mitigations are effective and assumptions hold? Think about unit, integration, performance, security, and failure injection tests. This section bridges the gap between risk identification and quality assurance.*

*   **Resilience & Failure Mode Testing:**
    *   [Test Case 1: e.g., "Simulate cache unavailability to verify graceful degradation of dependent services."]
    *   [Test Case 2: e.g., "Inject 'poison pill' data to ensure robust error handling and continuation of processing for valid data."]
*   **Data & Schema Validation Testing:**
    *   [Test Case 1: e.g., "Test data mapping logic with responses containing unexpected or missing fields."]
*   **Performance & Scalability Testing:**
    *   [Test Case 1: e.g., "Load test API endpoint X to ensure p99 latency remains below Y ms under Z RPS."]
*   **Configuration Testing:**
    *   [Test Case 1: e.g., "Verify application fails fast with clear errors if critical environment variables are missing or malformed."]

## 6. Monitoring and Observability Requirements

*Guidance for Cascade: Based on the identified risks and desired operational stability, define the essential monitoring and observability capabilities. What key metrics need to be tracked? What alerts are critical for detecting issues proactively? What kind of structured logging is required for effective troubleshooting? This section ensures the system is designed to be operable and maintainable.*

*   **Key Metrics to Track:**
    *   **Component A (e.g., Background Service):**
        *   [Metric 1: e.g., "Job success/failure rate"]
        *   [Metric 2: e.g., "Processing duration per item/batch"]
    *   **Component B (e.g., API Endpoint):**
        *   [Metric 1: e.g., "Request latency (p50, p90, p99)"]
        *   [Metric 2: e.g., "Error rate (4xx, 5xx)"]
*   **Critical Alerts (Examples - Thresholds TBD):**
    *   [Alert 1: e.g., "Component A job failure count > N in M minutes."]
    *   [Alert 2: e.g., "Component B p99 latency > X ms for Y minutes."]
*   **Structured Logging:**
    *   [Requirement 1: e.g., "All logs must be in JSON format."]
    *   [Requirement 2: e.g., "Include correlation ID, service name, timestamp, log level, and contextual data (e.g., relevant IDs)."]

## 7. Key Decisions & Changes Resulting from this Review

*Guidance for Cascade: Document the concrete, actionable changes made to the task plans or system design as a direct result of this pre-mortem review. For each change, explicitly state which risk(s) from Section 2 it is intended to mitigate. This creates clear traceability between problems and solutions.*

*   **For Task/Component X:**
    *   **Actions:** [Specific change 1 made to the task plan or design.]
    *   **Mitigates:** [Risk A (from Section 2), Risk B (from Section 2)]
    *   **Actions:** [Specific change 2 made to the task plan or design.]
    *   **Mitigates:** [Risk C (from Section 2)]

*   **For Task/Component Y:**
    *   **Actions:** [Specific change 1 made to the task plan or design.]
    *   **Mitigates:** [Risk D (from Section 2)]

## 8. Broader Lessons Learned / Insights Gained

*Guidance for Cascade: Reflect on the pre-mortem process itself. What broader insights or lessons were learned that could be applied to future projects or reviews? This could include observations about common risk patterns, effective review techniques, or architectural principles that were reinforced.*

*   [Lesson 1: e.g., "The 'Operator's Nightmare' lens consistently uncovers critical gaps in logging and error handling."]
*   [Lesson 2: e.g., "Explicitly defining data contracts early is crucial for preventing integration issues between services."]

## 9. Impact on Cascade's Understanding & Future Actions

*Guidance for Cascade: Describe how this review process has enhanced your understanding of the project, the Hangar Bay system, or specific technologies. What will you do differently or pay more attention to in future tasks as a result of this pre-mortem? This section is key for your continuous learning and improvement.*

*   **Refined Understanding:** [e.g., "This review deepened my understanding of the importance of idempotent operations in background services."]
*   **Proactive Application:** [e.g., "I will more proactively consider cache coherency issues when designing systems with multiple data stores."]
*   **Emphasis:** [e.g., "I will place a stronger emphasis on defining clear failure modes and recovery paths for all critical components."]

---
