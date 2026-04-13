---
name: Workspace Instructions
applyTo:
  - "*"
description: |
  Workspace-level instructions for AI agents in the EvalData repository.
  
  These instructions ensure agents follow project conventions, documentation policy, and workflow best practices. They are based on the documentation steward's policy and the current codebase structure.

principles:
  - Always link to existing documentation (Markdown or LaTeX) rather than duplicating content.
  - Keep diagrams and documentation top-to-bottom unless a different layout is clearly better.
  - Use the README as the main entry point for project overview, workflow, and navigation.
  - Place detailed architecture, workflow, and troubleshooting in docs/*.md, not in the README.
  - Place formal algorithmic explanations, equations, and derivations in docs/latex/.
  - Prefer visual documentation (figures, diagrams, tables) when it improves clarity.
  - Use built-in demo datasets for documentation figures and walkthroughs.
  - Do not invent features or describe planned work as implemented.
  - Do not embed algorithmic detail in Markdown when LaTeX is more appropriate.
  - Use compact tables or labeled figures for defining app semantics (e.g., column roles, dataset states) when it improves clarity.
  - For user-facing methods, explain practical meaning in Markdown, deeper technical detail in LaTeX if needed.
  - Keep prose concise and focused on what is needed around visuals and examples.
  - Do not use real user data in documentation unless explicitly required and privacy is clear.
  - When in doubt, prefer linking to docs/user-guide.md, docs/analysis-methods.md, docs/which-tool-when.md, or docs/latex/README.md.

anti-patterns:
  - Duplicating documentation content across files.
  - Overloading the README with deep technical or architectural detail.
  - Burying equations or algorithmic detail in Markdown when LaTeX is available.
  - Creating left-to-right diagrams unless the content clearly benefits from it.
  - Describing planned or unimplemented features as if they exist.
  - Using real user data in documentation without explicit need and privacy review.
  - Writing documentation that is not aligned with the current codebase or UI.

examples:
  - When asked for a workflow, link to docs/user-guide.md or docs/which-tool-when.md.
  - When asked for algorithmic detail, link to docs/latex/README.md or the relevant .pdf.
  - When asked for architecture, link to docs/technical-overview.md and use a top-to-bottom Mermaid diagram.
  - When asked about data formats, link to docs/data-formats.md.
  - When asked about column roles or dataset states, use a compact table or link to docs/glossary.md.
  - When asked for troubleshooting, link to docs/faq.md.
  - When asked for validation or test coverage, link to the relevant section in README.md.
  - When asked for build or packaging, link to the README.md build section and mention deploy.py.
