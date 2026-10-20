# Browser-hosted Empire Forge — implementation plan

This fork currently contains the original Flask application. Its HTML templates and static assets are served by Flask, and mod generation expects access to the user's local Age of Empires II: Definitive Edition data file. A Netlify static deployment alone will not run the Python routes or discover a file on a visitor's computer.

## Target architecture

- **Netlify frontend:** serve a browser UI and static assets.
- **Python API service:** run the existing Flask/Python mod-building code on a separate Python-capable host.
- **Explicit user upload:** users select and upload their own `empires2_x2_p1.dat` file when a mod build needs it; the hosted service must not assume it can read the user's local disk.
- **Download output:** return generated mod ZIPs as downloads. Temporary uploads and generated files should be removed after processing.
- **Browser-only civ editing:** preserve the ability to create/export `.civbuilder.json` files without requiring the user's installed game data where possible.

## Milestones

1. Audit all Flask routes and identify which can run without local filesystem paths.
2. Separate local-only game-data discovery from the mod build flow; add an upload-based input path with size/type validation and temporary-file cleanup.
3. Configure the API service, CORS, request limits, and temporary storage.
4. Create a Netlify-compatible frontend build and point its API requests at the hosted service.
5. Test civ JSON export, upload validation, mod ZIP generation, and download end-to-end.
6. Document environment variables and deploy steps; do not commit game data, secrets, or user uploads.

## Important constraints

- Do not publish proprietary Age of Empires game data in this repository or in a public server image.
- The Python backend is required for the existing mod-generation code; Netlify static hosting is only the frontend.
- Do not claim the hosted build works until the full upload-to-download flow has been tested.
