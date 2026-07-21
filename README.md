# AI Content Radar

## X fetch on Windows

Use the launcher below rather than calling `python` directly. It first tries normal commands, then resolves the Python Install Manager through the Windows App Paths registry; this keeps the scheduled job working when Microsoft Store app-execution aliases are invisible to the automation host.

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_x_fetch.ps1 -Date YYYY-MM-DD -MaxAccounts 8 -MaxQueries 2 -Limit 8
```

AI Content Radar is an automated AI intelligence briefing project. It collects public signals from developer communities, AI product updates, model/research sources, and social discussion, then turns them into a structured daily report published on GitHub Pages.

Live site: https://luoluozi996.github.io/ai-radar/

## What It Does

- Publishes a daily multi-page AI brief covering projects, tools, key events, model updates, research signals, and community discussion.
- Prioritizes actionable items over raw popularity by checking source quality, freshness, documentation, demos, and practical relevance.
- Keeps a public archive so each daily report remains reachable from a stable GitHub Pages entry point.
- Syncs selected entries to Notion with duplicate-key checks, and sends a WeChat notification after each run.

## Current Sections

- Project homepage: https://luoluozi996.github.io/ai-radar/
- Methodology and sources: https://luoluozi996.github.io/ai-radar/methodology.html
- Latest projects and tools: https://luoluozi996.github.io/ai-radar/projects/2026-07-20.html
- Latest key events: https://luoluozi996.github.io/ai-radar/news/2026-07-20.html
- Latest models and research: https://luoluozi996.github.io/ai-radar/models/2026-07-20.html
- Latest voices and discussion: https://luoluozi996.github.io/ai-radar/voices/2026-07-20.html
- Historical archive: https://luoluozi996.github.io/ai-radar/archive/
- X Watch sample: https://luoluozi996.github.io/ai-radar/x/2026-07-17.html

## Data Sources

The pipeline is designed to combine multiple public signals:

- GitHub repositories and README verification
- X API posts from selected AI builders, researchers, and product voices
- Hacker News and community discussions
- RSS feeds and official product blogs
- Model and paper sources such as Hugging Face, arXiv, and project documentation

Raw API responses and secrets are not published. Public pages only include curated, summarized, and source-linked entries.

## Selection Methodology

Items are selected by a practical editorial filter rather than raw popularity:

- Source traceability: original links, official docs, papers, READMEs, demos, or stable discussion URLs are preferred.
- User relevance: each item should explain who it affects and why it matters to ordinary AI users, builders, or learners.
- Evidence quality: hands-on posts, reproducible demos, technical docs, and multi-source confirmation are ranked above vague announcements.
- Practical value: the brief favors items that can change what to try, what to learn, what to avoid, or what to monitor.
- Noise control: duplicated hype, weakly sourced reposts, and purely promotional content are filtered or down-ranked.

Full methodology page: https://luoluozi996.github.io/ai-radar/methodology.html

## Workflow

1. Fetch public signals from configured sources.
2. Normalize and deduplicate items.
3. Filter low-quality, duplicated, or weakly sourced content.
4. Score items by freshness, evidence, practical value, and relevance.
5. Render static HTML pages for each daily section.
6. Publish to GitHub Pages and update the archive index.
7. Upsert Notion records by duplicate key.
8. Send a ServerChan WeChat notification with secret-safe logging.

## Engineering Highlights

- Static GitHub Pages output for reliable sharing and low maintenance.
- Multi-section report structure instead of a single flat list.
- Secret-safe local configuration for X API and ServerChan credentials.
- Local-only raw X cache, with filtered summaries published publicly.
- Duplicate-aware Notion synchronization to avoid repeated database rows.
- Automation memory log for run history, publish status, and push status.

## Repository Structure

```text
.
+-- index.html                 # Project homepage
+-- methodology.html           # Source, scoring, filtering, and safety explanation
+-- projects/                  # Daily project and tool reports
+-- news/                      # Daily key event reports
+-- models/                    # Daily model and research reports
+-- voices/                    # Daily community and opinion reports
+-- x/                         # Curated X Watch pages
+-- archive/                   # Historical report index
+-- assets/                    # Shared CSS and page assets
`-- data/                      # Public index data only
```

## Resume Summary

Built an automated AI intelligence pipeline that collects multi-source public signals, filters and ranks high-value items, generates a multi-page daily report, publishes it to GitHub Pages, syncs selected records to Notion, and sends WeChat notifications with secret-safe handling.

## Roadmap

- Improve source weighting for high-quality X and community discussion.
- Add a stronger public methodology page for scoring and filtering rules.
- Add lightweight analytics for report coverage and source diversity.
- Improve visual polish for report pages while keeping them fast and readable.
