# Architecture diagrams

System architecture for the Litigant Portal, authored in **draw.io** (diagrams.net).

## Files

- `system-architecture.drawio` — the source (uncompressed `mxGraphModel` XML). Edit in draw.io.
- `system-architecture.drawio.svg` — the render. This SVG shows as an image on GitHub and in Obsidian **and** reopens editable in draw.io (the diagram XML is embedded). It's what people view without opening the app.

## Editing

1. Install draw.io: `brew install --cask drawio`.
2. Open `system-architecture.drawio`, edit, save.
3. Keep it **uncompressed** so the source diffs cleanly: Extras → Edit Diagram shows plain XML; the file must stay a plain `<mxGraphModel>` (not a base64-deflate blob). draw.io preserves the format it opened.
4. Regenerate the SVG so the repo render stays in sync:

   ```sh
   drawio -x -f svg -e -o system-architecture.drawio.svg system-architecture.drawio
   ```

   (`-e` embeds the diagram so the SVG reopens editable.) Commit both files.

## What the diagram shows

C4 **Container** level, a technical / trust-boundary view for a new dev or a court's tech resource: the public edge (ingress + access gate), the per-court EKS instance as the isolation boundary (Django app, docassemble, Postgres + pgvector, Redis), the external boundary (AWS Bedrock via LiteLLM; third-party links), and delivery (CI/CD → EKS). AWS-managed services use AWS4 stencils; our own code (Django, docassemble) is a plain box.

Component-level zoom-ins per node are follow-on work.

## Why draw.io, not mermaid

Evaluated mermaid (#896). It can't produce this: mermaid's `architecture-beta` has AWS icons but a fixed, messy layout; a `flowchart` with the **ELK** layout composes cleanly and keeps edge labels, but the ELK renderer does **not** support icon shapes (icons render only under the default dagre renderer), so you get clean-layout *or* icons, never both. draw.io gives clean layout + AWS4 icons + edge labels together, self-contained (stencils ship with draw.io, no icon-pack bundle to vendor). The cost is manual layout and noisier SVG diffs, mitigated by the uncompressed `.drawio` source (clean diffs) plus the regenerated `.drawio.svg` (free GitHub/Obsidian render).
