# Reading Resources

Books + live robotics news. A simple static site with auto-updated news from top labs and industry voices.

**Live site:** [herronoui.github.io/reading-resources](https://herronoui.github.io/reading-resources)

## What's on the site

- **Robotics Pulse** — auto-curated news from arXiv, MIT, Stanford, Berkeley, IEEE, TechCrunch, Robohub, ROS Discourse, and more
- **Book shelf** — curated reading list for robotics, controls, aerospace, and math

## News feed

News is fetched automatically every 6 hours by a GitHub Action:

```bash
python scripts/fetch_news.py   # manual run
```

Output: `data/news.json` (committed by the workflow)

### Sources

| Voice | Source | Type |
| --- | --- | --- |
| Global Research | arXiv cs.RO | research |
| IEEE | IEEE Spectrum | industry |
| MIT | MIT News | labs |
| Stanford | Stanford HAI | labs |
| UC Berkeley | BAIR Blog | labs |
| Industry | The Robot Report, TechCrunch | industry |
| Community | Robohub, ROS Discourse | community |

## Run locally

```bash
open index.html
```

No build step.
