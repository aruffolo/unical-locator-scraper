# In-Repo Wave Marker

This folder stores git-tracked marker files for manual-correction waves.

Purpose:
- keep merge gates reproducible from a git-tracked path
- mirror essential evidence even when full wave reports stay outside this repo

Expected marker file name:
- `<wave-id>.md`

Minimum marker contents:
- wave ID
- date (UTC ISO8601)
- related commit hashes (scraper/backend/flutter)
- pointer to the full external wave report path
