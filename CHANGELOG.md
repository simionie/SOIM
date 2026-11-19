# SOIM

## Version 8.0.0-dev.3

- Add **Add Project** to the sidebar for registering existing projects inside or outside the workspace. Restore registered project paths from a browser cookie.
- Add `soim run --workers` for single-project runs. Share the starter's block processing and keep the daylight filter and output format. The default is one worker.

## Version 8.0.0-dev.2

- Add `soim-interface`, a local Flask interface for opening, creating, and editing projects. It serves on port 5050 by default and accepts `--port` to change it.
- Show Timeline first, with collapsible intervals, UTC date and time pickers, and a check that End is strictly later than Start. Use the bundled default instrument catalog when creating projects and offer project instruments in Timeline and Products.
- Share the product catalog between the simulator and the web editor. Show each mode and its CSV and shapefile destinations as checkboxes while preserving existing product aliases and the CSV format.
- Export `VelBor` mode `m` in m/s and preserve standard Corners exports alongside the experimental footprint branch.
- Run `soim-starter` on the open project and stream its console output to the page. Add local metakernel browsing and drag and drop, and remember the metakernel and worker count in the browser.
- Show the installed SOIM and Python versions in the footer and add VS Code extension recommendations.

## Version 7.0.0

- First release in Python.
