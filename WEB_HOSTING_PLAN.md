# Browser-hosted Empire Forge — implementation plan

This fork retains the original Flask app. Its templates and assets are served by Flask, and mod generation expects the user's local Age of Empires II: Definitive Edition data file. Netlify static hosting cannot run the Python routes or discover a visitor's local files.

## Milestone 1: static browser editor

The first prototype lives in `web/index.html`; `netlify.toml` configures Netlify to publish the `web` directory. It supports:
- Editing a civilization name, tagline, and description.
- Adding and removing bonus ideas.
- Marking tech-tree lines as planning notes.
- Exporting and importing its own JSON draft format.

**Compatibility note:** `empire-forge-browser-draft` is a temporary planning format, not the original application's compatible `.civbuilder.json` schema. The prototype warns users of this limitation. It is not yet a complete replacement for the original app and does not generate game mods.

## Target architecture

- **Netlify frontend:** host the browser UI and static assets.
- **Browser-only editing (next):** replace the prototype schema with the exact existing `.civbuilder.json` schema; reuse safe civ/bonus/tech-tree catalogs where possible.
- **Python API service (later):** run existing mod-generation code on a Python-capable host.
- **Explicit user upload (later):** users select and upload their own `empires2_x2_p1.dat` when a mod build needs it; never assume the hosted server can read their local disk.
- **Download output (later):** return generated mod ZIPs and clean temporary uploads and output files.

## Next milestones

1. Match the original `.civbuilder.json` schema and add import/export compatibility tests.
2. Reuse existing civilization and bonus catalogs in a browser-safe way without publishing proprietary game data.
3. Add automated checks for static build paths and import/export round trips.
4. Assess which original editor features can run in the browser without game data.
5. Later configure a Python API service for mod builds, CORS, request limits, upload validation, and temporary-file cleanup.
6. Test the relevant flows end-to-end before claiming deployment readiness.

## Important constraints

- Do not publish proprietary Age of Empires game data in this repository or a public server image.
- Netlify static hosting is for the frontend; the existing Python mod-generation code requires a Python-capable backend.
- Do not claim the hosted build works until the relevant flow has actually been tested.
