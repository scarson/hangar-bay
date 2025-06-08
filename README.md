# Hangar Bay

An EVE Online in-game asset marketplace, focusing initially on ship sales.

This project was inspired by a discussion[1] about the capabilities of AI coding assistants to deliver comprehensive software projects. It serves as an ongoing experiment and example project for developing and refining sophisticated software design specifications tailored for AI-assisted development. I am using [Windsurf Editor](https://windsurf.com/editor) with its [Cascade](https://windsurf.com/cascade) AI coding assistant (primarily using the [Google Gemini Pro 2.5](https://deepmind.google/models/gemini/pro/) model) to develop this project.

I aim to demonstrate how detailed, AI-centric specifications can guide AI coding assistants to produce high-quality, secure, and maintainable software.

A primary focus is to ensure that critical non-functional requirements—such as security, accessibility, testability, and observability—are consistently and rigorously addressed throughout the development lifecycle, particularly when working with AI coding assistants. Given concerns about AI coding assistant not producing especially secure code, I am especially interested in methods to get them to adhere to modern secure coding practices and incorporate security considerations into the design process. In this project, I'm attempting to do that by developing a security-spec.md that provides secure design principles tailored to the project, a checklist of security requirements, and AI implementation guidance for secure practices for the tech stack that it can (and must) reference while developing each feature. 


[1]: "I can see where GPT could be useful for code snippets, but I can't imagine it's able to deliver any sort of comprehensive outcome. If I say, "write me an ecommerce site for selling ships in eve online" theres no way its going to do that right? It's going to give me some template code about a shopping cart or something and thats it. Right?"
There's only one way to find out! 

## Project Documentation

For a comprehensive understanding of the Hangar Bay project, please refer to the following documents:

*   **[CONTRIBUTING.md](CONTRIBUTING.md):** Detailed guidelines for setting up your development environment, coding standards, version control workflows, testing procedures, dependency management, and specific instructions for AI assistants contributing to this project. **Start here if you plan to contribute or set up the project.**
*   **[`design/design-spec.md`](design/design-spec.md):** The main design specification, providing a comprehensive overview of the project's architecture, features, technology stack, and design principles.
*   **[`design/design-log.md`](design/design-log.md):** A chronological record of major design decisions, architectural changes, and significant process updates made throughout the project.
*   The `design/` directory contains further detailed specifications for various aspects of the application, including security, accessibility, testing, and individual features, all enhanced with AI-specific guidance.

## Core Technologies

*   **Backend:** Python with FastAPI
*   **Frontend:** Angular
*   **Database:** PostgreSQL
*   **Caching:** Valkey
*   **Authentication:** EVE Online SSO (OAuth 2.0)

## Implementation Plans - IN PROGRESS

To validate that detailed, AI-centric specifications can guide assistants to produce high-quality, secure, and maintainable software, we have to actually implement the plans. To that end, we are implementing an MVP of the Hangar Bay application, as outlined in the `plans/implementation/` directory.

The `plans/implementation/` directory contains implementation plans for the project, structured by phase and feature. Each plan is detailed in its own markdown file, providing a step-by-step guide to the development process.

**[`plans/implementation/00-mvp-implementation-plan-progress.md`](plans/implementation/00-mvp-implementation-plan-progress.md)** provides a progress log of the MVP implementation plan.
**[`plans/implementation/00-mvp-implementation-plan-overview.md`](plans/implementation/00-mvp-implementation-plan-overview.md)** provides a high-level overview of the MVP implementation plan.
**[`plans/implementation/phase-XX-phase-name/YY.Z-task-name.md`](plans/implementation/phase-XX-phase-name/YY.Z-task-name.md)** provides a detailed task file for a specific phase and task.

