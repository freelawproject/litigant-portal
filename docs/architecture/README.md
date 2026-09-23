# Architecture diagrams

System architecture for the Litigant Portal, authored in **draw.io** (diagrams.net).

## Files

Two diagrams, deliberately separate: one for how the portal runs **today**, one for **where it is going**. Conflating them is how a court partner ends up believing their data is already in its own account.

- `system-architecture.drawio` — **today.** What is actually deployed right now.
- `target-isolation.drawio` — **target (#859).** One AWS account per court. Not built yet.
- `eks-breakout.drawio` — component-level zoom into a court's instance internals.
- `corpus-pipeline.drawio` — **data flow.** How source documents become the topic flow
  pages and the assistant's prompt. Written up in [corpus-pipeline.md](corpus-pipeline.md).

Each has a committed `.drawio.svg` render alongside it. That SVG shows as an image on GitHub and in Obsidian **and** reopens editable in draw.io (the diagram XML is embedded) — it's what people view without opening the app.

## Editing

1. Install draw.io: `brew install --cask drawio`.
2. Open the `.drawio` file you want, edit, save.
3. Keep it **uncompressed** so the source diffs cleanly: Extras → Edit Diagram shows plain XML; the file must stay a plain `<mxGraphModel>` (not a base64-deflate blob). draw.io preserves the format it opened.
4. Regenerate the SVG so the repo render stays in sync:

   ```sh
   drawio -x -f svg -e -o system-architecture.drawio.svg system-architecture.drawio
   drawio -x -f svg -e -o target-isolation.drawio.svg target-isolation.drawio
   drawio -x -f svg -e -o corpus-pipeline.drawio.svg corpus-pipeline.drawio
   ```

   (`-e` embeds the diagram so the SVG reopens editable.) Commit both files.

### Wrapping a label under an icon

Icon shapes (AWS4, Kubernetes) put their caption below the shape, and by default that
caption renders as **one unwrapped line** — long ones run straight across neighbouring
boxes. `labelWidth` alone does not fix it: it sets the label's bounds, but the text only
wraps inside those bounds when `whiteSpace=wrap` is also set. draw.io enforces the same
pairing in its own UI — the Format panel greys out the labelWidth input unless the shape
has `whiteSpace=wrap` (`mxCellRenderer.getLabelBounds` sets the width; the renderer's wrap
flag is `"wrap" == style.whiteSpace`, which is unset by default).

So any icon shape with a caption longer than a couple of words wants **both**:

```
...;shape=mxgraph.aws4.resourceIcon;resIcon=mxgraph.aws4.rds;labelWidth=205;whiteSpace=wrap;
```

Use a literal `&#10;` only for a break you actually want (name line vs. description);
let `labelWidth` handle the rest, so the text reflows when it is edited.

## What `system-architecture.drawio` shows — today

C4 **Container** level, a technical / trust-boundary view for a new dev or a court's tech resource. Every node carries what it _does_, not just what it is:

- **Public edge** — the litigant's browser, and the ingress that terminates TLS and holds the site-wide access gate. The ingress splits by path: `/interview/*` goes to docassemble, everything else to Django.
- **FLP AWS account → shared EKS cluster → namespace `litigant`** — this is the part people get wrong. There is no per-court account today. The cluster's _name_ is `courtlistener` (that's the value of `EKS_CLUSTER_NAME` in `deploy.yml`, not a mislabel) — the portal is a tenant in it. Prod is the `litigant` namespace; QA is a second namespace, `qa-litigant`, in that same cluster, deployed by manual dispatch only.
- **The two workloads in the namespace** — the Django app (`litigant-web`), which is our code, and docassemble, which is **not**: it's the stock `jhpyle/docassemble` image, pulled and configured, running in its own container with its own database. That's why no arrow connects it to the app's Postgres. The diagram styles it as a dashed grey box for exactly that reason.
- **Managed AWS services** — Secrets Manager (app config + credentials, synced in by External Secrets), Postgres + pgvector (app data, corpus rows, chat threads, **and sessions** — Django's session backend is the database, not Redis), Redis/ElastiCache (Django's cache only), and S3 (a private bucket for litigant uploads, a public one for static + media).
- **External services** — AWS Bedrock for LLM inference, reached through LiteLLM, which is a _library inside the Django app_, not a service of its own. Third-party court and state services are **outbound links the litigant follows off-site** — there is no API integration with them.
- **Delivery** — GitHub Actions runs tests, builds the image, pushes it to **Docker Hub** (`freelawproject/litigant-portal:<sha>-prod`), then deploys to EKS. Prod deploys automatically on merge to main; QA is manual-dispatch only. The court corpus is YAML in this repo and ships **inside the image**, read at runtime.
- **Dev is not a court instance** — locally it's `docker compose`; the shared dev/demo host is a DigitalOcean droplet at `dev.litigantportal.com`. Neither is part of the deployed topology.

The diagram carries its own legend, bottom left: solid blue is our code, green is court-authored content, dashed grey is third-party software we merely pull and configure, purple is an AWS-managed service (drawn with its AWS4 stencil), and orange is external — the litigant leaves the portal.

## What `target-isolation.drawio` shows — the #859 target

Each court gets its **own AWS account**: pure data segmentation (no shared database, no shared bucket), per-court billing straight off the AWS invoice, independent version rollout, and fork-and-leave portability. Bedrock and the portal image stay shared across accounts; a shared docassemble is the one proposed exception, and the thing to re-argue against the model.

Still open, and marked on the diagram: whether each account runs EKS or ECS Fargate (**#859**), the per-court instance work itself (**#858**), how docassemble is hosted for QA and the court instances (**#888**), and that `DEPLOYMENT_ENV` validates against `{dev, qa, prod}` — a set four court instances do not fit.

## Why draw.io, not mermaid

Evaluated mermaid (#896). It can't produce this: mermaid's `architecture-beta` has AWS icons but a fixed, messy layout; a `flowchart` with the **ELK** layout composes cleanly and keeps edge labels, but the ELK renderer does **not** support icon shapes (icons render only under the default dagre renderer), so you get clean-layout _or_ icons, never both. draw.io gives clean layout + AWS4 icons + edge labels together, self-contained (stencils ship with draw.io, no icon-pack bundle to vendor). The cost is manual layout and noisier SVG diffs, mitigated by the uncompressed `.drawio` source (clean diffs) plus the regenerated `.drawio.svg` (free GitHub/Obsidian render).
