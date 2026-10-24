# MassWatt Presentation Scenes: Handoff

Context for continuing work on the MassWatt presentation in an AI coding tool. Keep this file beside the HTML and include it from `.kiro/steering/presentation.md` when working in Kiro.

## What It Is

An animated, recordable presentation for the MassWatt hackathon pitch (Hackachusetts 2026, Energy & Climate track). It visits four member buildings, then pulls back to the agent network that connects them:

1. **Office complex** (modeled on HouseZero): curtain wall behind wood fins, solar chimney, roof PV, rooftop heat pumps, battery yard
2. **Single-family home**: modern two-volume house, cutaway living room, balcony, roof PV, two wall-mounted home batteries, heat pump
3. **Corner café** (small business): brick storefront, awning, sidewalk tables, rooftop unit, walk-in cooler, no solar or battery
4. **Public library** (public institution): double-height reading hall behind white fins, roof PV, rooftop HVAC, shared community battery
5. **The network** (evening, 5–7 PM): every building pulls power at once, agents negotiate, the peak flattens

The visual style is a white-clay architectural model inspired by clean home-energy visualizations: charcoal roofs and solar panels, warm cutaway interiors, white context massing, soft long shadows and ambient occlusion, no trees, with glowing energy-flow lines and node dots on top.

## Files

| File | Role |
|---|---|
| `commonwatt-story.html` | **The presentation player.** Pre-rendered stills with energy lines, labels, smoke and the agent network drawn on top in SVG/HTML/CSS. No WebGL, works offline, light on any laptop. |
| `story-data.js` | `STORY`: every word, number, camera and label on screen. Shared by all pages. |
| `renders/` | `<chapter>.webp` stills (3200×1800) and `scenes.js` (where every flow line, label, node and smoke source lands on the 1600×900 frame). Generated; don't edit by hand. |
| `commonwatt-bake.html` | **The renderer.** Builds the 3D neighborhood with the kit and writes `renders/`. Soft shadows come from averaging 16 renders with the sun nudged around a small disk. |
| `commonwatt-kit.js` | **Reusable 3D kit**: materials, building models, people and furniture, energy lines, lighting moods, camera rig, stills and GLB export. Use it for any other MassWatt visual. |
| `commonwatt-live-3d.html` | The same story rendered live in WebGL (heavy). Useful for exploring cameras; also has Save still (4K) and Export 3D model (.glb). |
| `commonwatt-story.v1-backup.html` | The earlier 2D SVG version. |

- **No build step.** Open `commonwatt-story.html` in a browser.
- **What needs a re-render:** changing a camera, a building, a flow route, or a label anchor in `story-data.js`, or anything in `commonwatt-kit.js`. Open `commonwatt-bake.html`, click Render all scenes, and move the six downloaded files into `renders/`. Text, numbers, label names and event timing do not need a re-render; just reload.
- The renderer and live view load three.js r170 from jsDelivr, so they need internet. The player does not.
- **Fixed 1600×900 frame** scaled to fit like a video frame (`fit()`), so layout is identical at any screen size. Each scene slowly zooms toward its `cam.fx/fy` point and scenes crossfade.

## Where Things Live

### `STORY` (`story-data.js`): all words and numbers on screen

Edit content here only; never hardcode text or numbers elsewhere. All 3D points are `[east, up, south]` in meters.

- `illustrative`: shows the "Illustrative values" tag. Set to `false` once real results are in.
- `chapters[]`, one per scene:
  - `key`, `nav` (label in the scene bar), `mood` (`day` or `evening`), `clock`, `dur` (seconds)
  - `title`, `caption`: heading and subtitle at top left
  - `cam: {b, at, dist, az, el, fx, fy, drift}`: orbit target `at` (local to building `b`, or world if no `b`), distance in meters, azimuth from south toward east and elevation in degrees, where the target sits on the 1600×900 frame (also the zoom focus in the player), and a slow orbit in degrees per second (live view only)
  - `flows: [[id, kind, speed?]]`: energy lines switched on when the scene starts
  - `chips: [{b, at, place, name, value, kind, bar?, idle?}]`: dark labels. `at` is a named anchor of building `b` (below) or a local point; `bus: true` pins the label to the building's grid connection
  - `card: {agent, meta, title, body, offer, note, limits}`: the agent status card
- The network chapter adds `meters`, `events[]` and `relieve: {flows, smoke}` (unchanged from v1).
- `STORY.network.coord`: world point where the commons coordinator node floats.

Named anchors: office `pv hp battery building facade top`; home07 `pv battery hp home top`; gable houses `pv battery hp house top`; cafe `hvac cooler cafe top`; library `pv hvac battery library top`; grid `top`.

### Network event types

| Field | Effect |
|---|---|
| `clock: '5:30 PM'` | Update the on-screen clock |
| `caption: '...'` | Replace the subtitle |
| `log: [time, who, text, tone]` | Add a row to the message log (8 rows max). Tones: `info`, `ask`, `req`, `ok`, `counter`, `block`, `join`, `receipt` |
| `nodes: true` | Show the coordinator, grid, and member nodes (library stays hidden until it joins) |
| `msg: [from, to]` | Animate a message along the arc between the coordinator and a node |
| `block: nodeId` | A request stopped by that member's trust guard (red flash, "blocked") |
| `join: nodeId` | A node joins live with a pop-in |
| `relieve: true` | Apply `relieve` flows, meters, and smoke level |

Node ids: `coord`, `office`, `home03`, `home05`, `home07`, `cafe`, `library`, `grid`. Nodes float above each building's `top` anchor; `STORY.network.nudge` shifts crowded nodes by screen pixels. A `block` event can carry a `reason`, shown under the node.

### The 3D kit (`commonwatt-kit.js`)

`window.CommonwattKit(THREE, addons)` returns the kit. The story page shows how to load it.

- **`createStage(canvas, {ao})`**: renderer, lights, GTAO ambient occlusion, camera rig. Returns `stage` with:
  - `place(key, x, z, BUILD.fn, opts)`: add a building at a world position; its anchors, flows and service point become world coordinates in `stage.B[key]`
  - `addFlow(id, points)`, `setFlow(id, kind | null, speed?)`, `allFlowsOff()`: energy lines. Kinds: `solar` (green), `battery` (amber), `grid` (teal), `strain` (red), `signal` (indigo); colors in `PAL`
  - `setCamera(cam, instant)`, `setMood('day' | 'evening')`, `setSmoke(level)`, `update(dt)`, `render()`, `project(worldPoint)` → frame pixels
  - `saveStill(name, scale)`: PNG of the 3D render without labels (2.4 → 3840×2160); `exportGLB(name)`: the whole neighborhood as a `.glb` for Blender, Keynote or Figma
- **`buildNeighborhood(stage)`**: the demo blocks in Cambridge, laid out like a real distribution grid:
  - **Main St** (commercial corridor): the office, the corner café (Main St & Elm St) and storefront blocks; the underground primary feeder (`bus`) runs under its north sidewalk from the substation.
  - **Elm St** (residential side street): home_03 and home_05 on the west side, home_07 on the east side, all facing the street. An overhead lateral on wood poles (`bus_elm`) feeds a pole-top transformer; each house gets an overhead service drop.
  - **Oak St / Broadway**: an underground lateral (`bus_oak`) runs up Oak St to the library's civic site on Broadway.
  - White-model context: triple-deckers and gable houses with windows, porches and cornices (`BUILD.ctxHouse`) and storefront blocks (`BUILD.ctxShop`) fill the blocks; their windows glow at night.
  - home_03 has an EV with a bidirectional charger (`ev`, `evCharger`, flow `h3_ev_home`); its trust guard blocks the −3 kW request because the EV must reach 80% by 7 AM.
- **`place(key, x, z, BUILD.fn, opts, seed, ry)`**: `ry` rotates a building to face its street; anchors, flows and `cam.at` offsets rotate with it.
- **`BUILD.*`**: `office`, `modernHome`, `gableHouse({pv, battery, hp, ev})`, `cafe`, `library`, `substation`, `tower`, `plant`, `pole({transformer})`, `ctxHouse`, `ctxShop`. Each draws into a `Builder` in local meters (front faces +z) and returns `{anchors, flows, svc}`.
- **Builder helpers**: `box`, `boxC`, `cyl`, `disk`, `sphere`, `seg`, `tree`, `shrub`; facade `win(bb, FACE(axis, at), u0, u1, v0, v1, opts)`; people `figure(bb, x, y, z, ry, 'stand' | 'walk' | 'sit')`; furniture `sofa`, `table`, `roundTable`, `chair`, `bookshelf`, `potPlant`; equipment `pvArray`, `heatPump`, `homeBattery`, `rooftopUnit`, `fence`. Parts merge into one mesh per material, so detail stays cheap.
- **Materials** in `MAT`; day and evening lighting in `MOOD`. Window glow (`room`, `roomDim`), interior lamps and street-light pools fade in with the evening mood.

### Energy line ids

- office: `o_solar_bat`, `o_bat_bldg`, `o_solar_bldg`
- home: `h7_solar_bat`, `h7_solar_home`, `h7_bat_home`, `h7_hp`, `h5_bat_home`
- café: `c_cooler`, `c_hvac`
- library: `l_solar_bat`, `l_bat_lib`, `l_solar_lib`
- drops: `<member>_in` (grid to building) and `<member>_out` (building to grid), for `office`, `home03`, `home05`, `home07`, `cafe`, `library`
- grid: `trunk` (power plant along the transmission line to the substation), `bus` (Main St feeder), `bus_elm` (Elm St overhead lateral), `bus_oak` (Oak St lateral to the library)
- home_03 EV: `h3_ev_home`

### Other parts

- **Controls** sit below the frame so recordings stay clean: Previous, Play/Pause, Next, Full screen, and a link to the live 3D view. Space plays or pauses; arrow keys change scenes.
- **Debug hook:** `window.commonwatt.go(sceneIndex, seconds)` jumps to any moment, paused. Also `play()`, `pause()`, `story`, `renders`.
- **Reduced motion:** with `prefers-reduced-motion`, the slow zoom, line dashes and smoke stop.
- **Foliage and people:** `kit.options.foliage` and `kit.options.people` are `false` (no trees, shrubs or human figures). Set them to `true` before `buildNeighborhood()` to bring them back.
- **Home scene** looks along Elm St: home_07 in front, and home_03's EV with its bidirectional charger across the street, labeled `EV · home_03`.
- **Caching:** the player, renderer and live view add a timestamp when loading `story-data.js`, the kit and `renders/scenes.js`, so a normal reload always picks up edits and new renders.

## Next Tasks

1. **Use real simulation results.** Load a results file and build the network chapter from it instead of hardcoded values. Suggested shape:
   ```json
   {
     "ask_kw": 50,
     "window": "17:00-19:00",
     "members": {
       "office":  {"request_kw": 18,  "response": "accept",  "kw": 18},
       "home07":  {"request_kw": 2.0, "response": "counter", "kw": 1.2, "reason": "comfort limit"},
       "home03":  {"request_kw": 3.0, "response": "blocked", "reason": "exceeds limit"},
       "home05":  {"request_kw": 2.3, "response": "accept",  "kw": 2.3},
       "cafe":    {"request_kw": 3.5, "response": "accept",  "kw": 3.5},
       "library": {"joins": true,     "response": "accept",  "kw": 25}
     },
     "receipts": [{"member": "home07", "kwh": 2.4, "usd": 0.62}],
     "meters": {"local_before": 31, "local_after": 68, "peak_before": 100, "peak_after": 64}
   }
   ```
   Generate `events[]`, chip values, and card offers from it, keep the timing spacing, then set `illustrative: false`.
2. **Keep the numbers consistent.** The accepted amounts must add up to the committed total; in the current illustrative data, 18 + 1.2 + 2.3 + 3.5 + 25 = 50 kW.
3. **Record the demo.** Full screen, 1080p at 60 fps, with a voiceover. The full run is about 55 seconds; pause on cards while narrating.
4. **Reuse the kit** for the coordination-system design: `stage.place()` any `BUILD.*` model, draw your own flows with `addFlow`, and export stills or GLB.

## Constraints

- No build step. The player must keep working offline with no WebGL; heavy work belongs in the renderer.
- Keep all on-screen text and numbers in `STORY`.
- Members are large buildings, households, small businesses, and public institutions. One household (home_03) has an EV with a bidirectional charger; keep EVs to that role.
- Use generic product names ("home battery", not a brand name).
- Label anything not measured as illustrative or simulated.

## Hackathon Rule to Remember

Hackachusetts requires projects to be built with Kiro, and judges score how Kiro was used (specs, steering docs, hooks, MCP, property-based tests). Insufficient use of Kiro can lead to disqualification. Work on anything in the submitted repository should happen in Kiro so it counts toward that score.
