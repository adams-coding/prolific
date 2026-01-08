from __future__ import annotations

import json
from pathlib import Path


VIZ_DIRNAME = "viz"
PAGES_DIRNAME = "docs"
EVENTS_FILENAME = "events.json"
INDEX_FILENAME = "index.html"
CSS_FILENAME = "style.css"
JS_FILENAME = "app.js"


def viz_paths(repo_path: Path) -> tuple[Path, Path]:
    viz_dir = repo_path / VIZ_DIRNAME
    return viz_dir / INDEX_FILENAME, viz_dir / EVENTS_FILENAME


def pages_paths(repo_path: Path) -> tuple[Path, Path]:
    pages_dir = repo_path / PAGES_DIRNAME
    return pages_dir / INDEX_FILENAME, pages_dir / EVENTS_FILENAME


def viz_asset_paths(repo_path: Path) -> tuple[Path, Path]:
    viz_dir = repo_path / VIZ_DIRNAME
    return viz_dir / CSS_FILENAME, viz_dir / JS_FILENAME


def pages_asset_paths(repo_path: Path) -> tuple[Path, Path]:
    pages_dir = repo_path / PAGES_DIRNAME
    return pages_dir / CSS_FILENAME, pages_dir / JS_FILENAME


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def _atomic_write_json(path: Path, payload) -> None:
    _atomic_write_text(path, json.dumps(payload, indent=2, sort_keys=True))


def ensure_viz_index_html(repo_path: Path) -> Path:
    index_path, events_path = viz_paths(repo_path)
    pages_index_path, pages_events_path = pages_paths(repo_path)

    # Self-contained, offline HTML (no CDN). Reads ./events.json and draws an animated
    # "project system" visualization:
    # - Core bubble: each watch folder (project)
    # - Event bubble: each run/event (connected to its project core)
    # - Satellite bubbles: per-language and assets for that event (connected to event)
    # - Dark background, floating motion + parallax while scrolling
    #
    # NOTE: We intentionally overwrite index.html so visual updates deploy to GitHub Pages.
    # Bump this whenever the generated HTML changes so users can verify deploys.
    viz_version = 31

    # IMPORTANT:
    # Do NOT use an f-string for this HTML blob. The embedded CSS/JS contains many `{}` braces
    # which will break Python string interpolation/parsing.
    html = """<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Prolific: Git Active</title>
    <style>
      :root { color-scheme: dark; }
      html, body { height: 100%; }
      body {
        margin: 0;
        font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif;
        background: radial-gradient(1200px 800px at 30% 20%, #171a22 0%, #0b0c10 45%, #07080b 100%);
        color: #e7e9ee;
        overflow-x: hidden;
      }
      header {
        position: sticky;
        top: 0;
        z-index: 10;
        backdrop-filter: blur(10px);
        background: color-mix(in srgb, #0b0c10 82%, transparent);
        border-bottom: 1px solid color-mix(in srgb, #fff 10%, transparent);
      }
      .topbar {
        display: flex;
        flex-wrap: wrap;
        gap: 14px;
        align-items: center;
        justify-content: space-between;
        padding: 14px 18px;
      }
      .brand { display: flex; gap: 12px; align-items: baseline; }
      h1 { font-size: 16px; margin: 0; letter-spacing: 0.2px; }
      .sub { opacity: 0.75; font-size: 13px; }
      .controls { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
      select, button {
        padding: 7px 10px;
        border-radius: 10px;
        border: 1px solid color-mix(in srgb, #fff 14%, transparent);
        background: color-mix(in srgb, #0b0c10 65%, transparent);
        color: #e7e9ee;
        cursor: pointer;
      }
      button:hover { border-color: color-mix(in srgb, #fff 22%, transparent); }
      .pill {
        padding: 6px 10px;
        border-radius: 999px;
        border: 1px solid color-mix(in srgb, #fff 14%, transparent);
        opacity: 0.85;
        font-size: 12px;
      }
      .stage {
        position: fixed;
        inset: 0;
        z-index: 0;
      }
      canvas {
        position: absolute;
        inset: 0;
        display: block;
        width: 100%;
        height: 100%;
      }
      .hint {
        position: absolute;
        left: 18px;
        bottom: 14px;
        font-size: 12px;
        opacity: 0.65;
        max-width: min(720px, calc(100vw - 36px));
        line-height: 1.35;
      }
      .tooltip {
        position: fixed;
        pointer-events: none;
        background: color-mix(in srgb, #0b0c10 85%, transparent);
        color: #e7e9ee;
        border: 1px solid color-mix(in srgb, #fff 16%, transparent);
        border-radius: 12px;
        padding: 10px 12px;
        font-size: 12px;
        max-width: 420px;
        display: none;
        box-shadow: 0 10px 30px rgba(0,0,0,0.35);
      }
      .badge {
        display: inline-block;
        padding: 2px 8px;
        border-radius: 999px;
        border: 1px solid color-mix(in srgb, #fff 18%, transparent);
        margin-right: 8px;
        opacity: 0.9;
      }
    </style>
  </head>
  <body>
    <header>
      <div class="topbar">
        <div class="brand">
          <h1>Prolific: Git Active</h1>
          <div class="sub">Project systems (metadata only, no file content reads)</div>
        </div>
        <div class="controls">
          <button id="reload">Reload</button>
          <button id="zoom-out" title="Zoom out">-</button>
          <button id="zoom-reset" title="Reset zoom">100%</button>
          <button id="zoom-in" title="Zoom in">+</button>
          <div class="pill" id="count"></div>
          <div class="pill" id="ver">viz v__VIZ_VERSION__</div>
        </div>
      </div>
    </header>

    <div class="stage">
      <canvas id="c"></canvas>
      <div class="hint">
        Scroll for parallax depth. Big bubbles are projects (watch folders). Smaller bubbles are activity events and per-language satellites.
        Nothing here includes file names/paths or file contents—only aggregates by extension and size deltas.
      </div>
    </div>

    <div class="tooltip" id="tooltip"></div>

    <script>
      // Visualization version: 2 (project systems + parallax)
      const canvas = document.getElementById('c');
      const ctx = canvas.getContext('2d');
      const tooltip = document.getElementById('tooltip');
      const countEl = document.getElementById('count');
      const verEl = document.getElementById('ver');
      const METRIC = 'net_loc_estimate'; // fixed metric for bubble sizing (keep UI simple)
      if (verEl) verEl.textContent = 'viz v__VIZ_VERSION__';

      // Zoom state
      let zoomLevel = 1.0; // 1.0 = 100%, can range from 0.1 to 3.0
      let targetZoom = 1.0;
      const ZOOM_MIN = 0.1;
      const ZOOM_MAX = 3.0;
      const ZOOM_STEP = 0.1;
      const ZOOM_SMOOTH = 0.15; // Smooth interpolation factor

      function clamp(v, lo, hi) {
        const n = Number(v);
        if (!Number.isFinite(n)) return lo;
        return Math.max(lo, Math.min(hi, n));
      }
      function lerp(a, b, t) { return a + (b - a) * t; }

      function parseEventTime(e) {
        const s = String(e.event_id || '');
        const d = new Date(s);
        return isNaN(d.getTime()) ? new Date(0) : d;
      }

      function fmt(n) {
        if (typeof n !== 'number') return String(n);
        const abs = Math.abs(n);
        if (abs >= 1e9) return (n/1e9).toFixed(1) + 'B';
        if (abs >= 1e6) return (n/1e6).toFixed(1) + 'M';
        if (abs >= 1e3) return (n/1e3).toFixed(1) + 'K';
        return String(Math.round(n));
      }

      function num(v, fallback=0) {
        const n = Number(v);
        return Number.isFinite(n) ? n : fallback;
      }

      function hashColor(str) {
        // Vibrant planetary/nebula colors for languages
        const planetaryColors = {
          // Programming languages - vibrant nebula colors
          'Python': '#00FF7F',        // Plasma Green
          'JavaScript': '#FFD700',    // Gold (Saturn)
          'TypeScript': '#0080FF',    // Electric Blue
          'Java': '#FF6B35',          // Mars Orange
          'C': '#8A2BE2',             // Laser Purple
          'C++': '#9B59B6',           // Deep Purple
          'C#': '#A855F7',            // Vivid Purple
          'Go': '#00D9FF',            // Cyan (Uranus)
          'Rust': '#FF4500',          // Rust Orange-Red
          'Ruby': '#E40066',          // Ruby Red
          'PHP': '#7B68EE',           // Medium Slate Blue
          'Swift': '#FF8C00',         // Dark Orange
          'Kotlin': '#B65FCF',        // Violet
          'R': '#276FBF',             // R Blue
          'Scala': '#DC322F',         // Scala Red
          'Shell': '#89E051',         // Terminal Green
          'Bash': '#4EAA25',          // Bash Green
          'HTML': '#E34C26',          // HTML Orange
          'CSS': '#563D7C',           // CSS Purple
          'SCSS': '#BF4080',          // SCSS Pink
          'Vue': '#42B883',           // Vue Green
          'React': '#61DAFB',         // React Cyan
          'Svelte': '#FF3E00',        // Svelte Orange
          'SQL': '#F29111',           // SQL Orange
          'Lua': '#000080',           // Navy Blue
          'Perl': '#0298C3',          // Perl Blue
          'Dart': '#0175C2',          // Dart Blue
          'Julia': '#9558B2',         // Julia Purple
          'Elixir': '#6E4A7E',        // Elixir Purple
          'Haskell': '#5E5086',       // Haskell Purple
          'Clojure': '#5881D8',       // Clojure Blue
          'Erlang': '#B83998',        // Erlang Magenta
          'Markdown': '#083FA1',      // MD Blue
          'JSON': '#02569B',          // JSON Blue
          'XML': '#0060AC',           // XML Blue
          'YAML': '#CB171E',          // YAML Red
          // Assets - vibrant cosmic colors (NO GREY!)
          'Assets': '#FF0090',        // Neon Magenta
          'Unknown': '#FF6EC7',       // Hot Pink
        };
        
        const normalized = String(str).trim();
        if (planetaryColors[normalized]) {
          return planetaryColors[normalized];
        }
        
        // Fallback: vibrant HSL for unknown languages
        let h = 2166136261;
        for (let i=0; i<normalized.length; i++) {
          h ^= normalized.charCodeAt(i);
          h = Math.imul(h, 16777619);
        }
        const hue = Math.abs(h) % 360;
        return `hsl(${hue} 85% 65%)`; // More saturated and lighter
      }

      function rgba(hexOrHsl, a) {
        // Use CSS color-mix fallback by drawing with globalAlpha instead.
        return hexOrHsl;
      }

      const langColor = (lang) => {
        // All colors come from hashColor - NO HARDCODED GREY!
        if (!lang) return '#FF6EC7'; // Hot Pink for undefined
        return hashColor(lang);
      };
      
      // Color manipulation helpers for glow effects
      function lightenColor(color, amount) {
        // Parse hex color and increase brightness
        if (color.startsWith('#')) {
          const hex = color.slice(1);
          const r = parseInt(hex.slice(0, 2), 16);
          const g = parseInt(hex.slice(2, 4), 16);
          const b = parseInt(hex.slice(4, 6), 16);
          
          const newR = Math.min(255, Math.floor(r + (255 - r) * amount));
          const newG = Math.min(255, Math.floor(g + (255 - g) * amount));
          const newB = Math.min(255, Math.floor(b + (255 - b) * amount));
          
          return `rgb(${newR}, ${newG}, ${newB})`;
        }
        return color;
      }
      
      function darkenColor(color, amount) {
        // Parse hex color and decrease brightness
        if (color.startsWith('#')) {
          const hex = color.slice(1);
          const r = parseInt(hex.slice(0, 2), 16);
          const g = parseInt(hex.slice(2, 4), 16);
          const b = parseInt(hex.slice(4, 6), 16);
          
          const newR = Math.floor(r * (1 - amount));
          const newG = Math.floor(g * (1 - amount));
          const newB = Math.floor(b * (1 - amount));
          
          return `rgb(${newR}, ${newG}, ${newB})`;
        }
        return color;
      }

      // Scene state
      let eventsCache = [];
      let nodes = [];   // {id,type,label,x,y,z,vx,vy,r,color,meta,locked}
      let links = [];   // {a,b,rest,k}
      let stars = [];
      let lastT = performance.now();
      let mouse = { x: 0, y: 0, down: false };
      let hovered = null;
      let DPR = 1;
      let CSS_W = 0;
      let CSS_H = 0;

      function resize() {
        const dpr = Math.max(1, Math.min(2, window.devicePixelRatio || 1));
        const rect = canvas.getBoundingClientRect();
        const cssW = Math.max(1, Math.floor(rect.width || window.innerWidth || 1));
        const cssH = Math.max(1, Math.floor(rect.height || window.innerHeight || 1));
        const w = Math.max(1, Math.floor(cssW * dpr));
        const h = Math.max(1, Math.floor(cssH * dpr));
        DPR = dpr;
        CSS_W = cssW;
        CSS_H = cssH;
        canvas.width = w;
        canvas.height = h;
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      }

      function scrollY() {
        return window.scrollY || 0;
      }

      function ensureStars() {
        const w = CSS_W || window.innerWidth || canvas.clientWidth || 1;
        const h = CSS_H || window.innerHeight || canvas.clientHeight || 1;
        const target = Math.floor((w*h) / 18000);
        if (stars.length >= target) return;
        for (let i=stars.length; i<target; i++) {
          stars.push({
            x: Math.random() * w,
            y: Math.random() * h,
            z: lerp(0.15, 0.9, Math.random()),
            r: lerp(0.6, 1.6, Math.random()),
            a: lerp(0.08, 0.25, Math.random()),
          });
        }
      }

      function buildScene(events) {
        events = [...events].sort((a, b) => parseEventTime(a) - parseEventTime(b));
        eventsCache = events;
        countEl.textContent = `${events.length} event${events.length === 1 ? '' : 's'}`;

        nodes = [];
        links = [];

        // Build "project cores"
        const projectLabels = new Map(); // label -> id
        for (const e of events) {
          const wfs = Array.isArray(e.watch_folders) ? e.watch_folders : [];
          for (const w of wfs) {
            const label = String(w || 'project');
            if (!projectLabels.has(label)) {
              projectLabels.set(label, `p:${label}`);
            }
          }
        }
        if (projectLabels.size === 0) {
          projectLabels.set('project', 'p:project');
        }

        const projects = [...projectLabels.entries()];
        const w = CSS_W || window.innerWidth || canvas.clientWidth || 1;
        const h = CSS_H || window.innerHeight || canvas.clientHeight || 1;
        
        // Group events by project FIRST to calculate sizes
        const eventsByProject = new Map();
        for (const e of events) {
          const wfs = Array.isArray(e.watch_folders) && e.watch_folders.length ? e.watch_folders : ['project'];
          for (const wf of wfs) {
            const key = String(wf);
            if (!eventsByProject.has(key)) eventsByProject.set(key, []);
            eventsByProject.get(key).push(e);
          }
        }
        
        // Galactic center - projects orbit around this
        const galaxyCenter = {
          x: w * 0.5,
          y: h * 0.5,
        };
        
        // Position projects in orbit around galactic center
        const projectSize = 40; // Project core radius (reduced from 60)
        const baseOrbitRadius = 280; // Starting orbit distance
        const orbitIncrement = 180; // Distance between each orbital ring
        
        projects.forEach(([label, id], idx) => {
          const projectEvents = eventsByProject.get(label) || [];
          
          // Spiral outward: each project gets its own orbital ring
          const ring = Math.floor(idx / 6); // 6 projects per ring
          const posInRing = idx % 6;
          const projectOrbitRadius = baseOrbitRadius + (ring * orbitIncrement);
          const projectsInRing = Math.min(6, projects.length - (ring * 6));
          
          // Position project in orbit around galactic center
          const theta = (posInRing / Math.max(projectsInRing, 1)) * Math.PI * 2;
          const projectX = galaxyCenter.x + Math.cos(theta) * projectOrbitRadius;
          const projectY = galaxyCenter.y + Math.sin(theta) * projectOrbitRadius;
          
          // Vibrant planetary colors for projects
          const projectColors = [
            '#0080FF',  // Electric Blue (Neptune)
            '#FFD700',  // Gold (Saturn)
            '#00D9FF',  // Cyan (Uranus)
            '#FF6B35',  // Mars Orange
            '#9B59B6',  // Deep Purple (Jupiter)
            '#00FF7F',  // Plasma Green
            '#FF0090',  // Neon Magenta
            '#8A2BE2',  // Laser Purple
          ];
          const projectColor = projectColors[idx % projectColors.length];
          
          nodes.push({
            id,
            type: 'project',
            label,
            x: projectX,
            y: projectY,
            z: 0.5,
            vx: 0, vy: 0,
            r: projectSize,
            color: projectColor,
            meta: { 
              projectIdx: idx,
              eventCount: projectEvents.length,
              parentId: 'galaxy', // Special parent ID for galactic center
              orbitRadius: projectOrbitRadius,
              orbitAngle: theta,
              orbitSpeed: 0.03, // Slow rotation for projects
              galaxyCenter: galaxyCenter,
            },
            locked: false,
          });
        });
        
        // Set page height to fit content - account for outermost orbital ring
        const maxRing = Math.floor(projects.length / 6);
        const maxOrbitRadius = baseOrbitRadius + (maxRing * orbitIncrement);
        const maxProjectY = maxOrbitRadius + 180 + 140 + 60; // orbit + events + satellites
        document.body.style.height = `${Math.max(window.innerHeight, galaxyCenter.y + maxProjectY + 200)}px`;

        // Group events by project, then position in circular orbits
        const metric = METRIC;
        let maxAbs = 1;
        for (const e of events) {
          maxAbs = Math.max(maxAbs, Math.abs(num(e?.[metric], 0)));
        }

        function addNode(n) { nodes.push(n); return n; }
        function addLink(a, b, rest, k) { links.push({ a, b, rest, k }); }
        function getNode(id) { return nodes.find(n => n.id === id); }

        // Position events in circular orbits around their project cores
        // Process each project separately to distribute events evenly in a full circle
        projects.forEach(([projectLabel, projectId]) => {
          const projectEvents = eventsByProject.get(projectLabel) || [];
          if (projectEvents.length === 0) return;

          const pNode = getNode(projectId);
          if (!pNode) return;

          // Distribute THIS project's events evenly in a full 360° circle
          projectEvents.forEach((e, eventIdx) => {
            const metricVal = num(e?.[metric], 0);
            const vAbs = Math.abs(metricVal);
            
            // Calculate angle based on position within THIS project's events
            const theta = (eventIdx / Math.max(projectEvents.length, 1)) * Math.PI * 2;

            const eventId = `e:${e.event_id}:${projectLabel}`;
            const baseR = 8 + Math.sqrt(vAbs / maxAbs) * 18; // Reduced from 12 + 28
            const r = baseR * (0.95 + Math.random() * 0.1); // ±5% randomization
            
            // Slightly randomize orbit distance for natural variation
            const baseOrbitRadius = 180;
            const eventOrbitRadius = baseOrbitRadius * (0.92 + Math.random() * 0.16); // ±8% variation
            
            // Position event in circular orbit around THIS project core
            const evX = pNode.x + Math.cos(theta) * eventOrbitRadius;
            const evY = pNode.y + Math.sin(theta) * eventOrbitRadius;
            
            // Vibrant nebula colors for events (positive = cyan/green, negative = magenta/orange)
            const eventColor = metricVal >= 0 
              ? (vAbs > maxAbs * 0.5 ? '#00FFD9' : '#00FF7F')  // High activity: Cyan, Medium: Plasma Green
              : (vAbs > maxAbs * 0.5 ? '#FF0090' : '#FF6B35'); // High activity: Neon Magenta, Medium: Orange
            
            const ev = addNode({
              id: eventId,
              type: 'event',
              label: String(e.event_id || ''),
              x: evX,
              y: evY,
              z: lerp(0.35, 1.0, Math.random()),
              vx: 0, vy: 0,
              r,
              color: eventColor,
              meta: { 
                event: e,
                parentId: projectId,
                orbitRadius: eventOrbitRadius,
                orbitAngle: theta,
                orbitSpeed: 0.1 // Events rotate around projects
              },
              locked: false,
            });
            // Link with correct rest distance (since we use cos/sin for both X and Y, distance = radius)
            addLink(pNode.id, ev.id, eventOrbitRadius, 0.012);

            // Satellites by language (top 4 by abs delta bytes)
            const langs = Array.isArray(e.languages) ? e.languages : [];
            const top = [...langs]
              .sort((a,b) => Math.abs(num(b?.delta_bytes, 0)) - Math.abs(num(a?.delta_bytes, 0)))
              .slice(0, 4);

            top.forEach((l, k) => {
              const lang = String(l.language || 'Unknown');
                const delta = num(l?.delta_bytes, 0);
              const baseRR = 4 + Math.sqrt(Math.abs(delta) / Math.max(1, maxAbs)) * 7; // Reduced from 6 + 10
              const rr = baseRR * (0.93 + Math.random() * 0.14); // ±7% randomization
              const sid = `s:${eventId}:${lang}:${k}`;
              // Satellite orbit distance with slight randomization
              const baseSatOrbit = 40 + (rr * 2);
              const satOrbit = baseSatOrbit * (0.90 + Math.random() * 0.20); // ±10% variation
              const a = (k / Math.max(top.length, 1)) * Math.PI * 2;
              const sn = addNode({
                id: sid,
                type: 'sat',
                label: lang,
                x: ev.x + Math.cos(a) * satOrbit,
                y: ev.y + Math.sin(a) * satOrbit,
                z: lerp(0.55, 1.0, Math.random()),
                vx: 0, vy: 0,
                r: rr,
                color: langColor(lang),
                meta: { 
                  delta_bytes: delta,
                  parentId: eventId,
                  orbitRadius: satOrbit,
                  orbitAngle: a,
                  orbitSpeed: 0.2 // Satellites rotate faster around events
                },
                locked: false,
              });
              // Satellite orbits: use calculated satOrbit distance
              addLink(ev.id, sn.id, satOrbit, 0.04);
            });

            // Asset satellite if unknown bytes changed
            const unknown = num(e?.unknown_delta_bytes, 0);
            if (unknown !== 0) {
              const baseRR = 5 + Math.sqrt(Math.abs(unknown) / Math.max(1, maxAbs)) * 7; // Reduced from 7 + 10
              const rr = baseRR * (0.93 + Math.random() * 0.14); // ±7% randomization
              // Orbit distance with slight randomization
              const baseSatOrbit = 40 + (rr * 2);
              const satOrbit = baseSatOrbit * (0.90 + Math.random() * 0.20); // ±10% variation
              const a = (top.length / (top.length + 1)) * Math.PI * 2;
              const sid = `s:${eventId}:Assets`;
              const sn = addNode({
                id: sid,
                type: 'sat',
                label: 'Assets',
                x: ev.x + Math.cos(a) * satOrbit,
                y: ev.y + Math.sin(a) * satOrbit,
                z: lerp(0.55, 1.0, Math.random()),
                vx: 0, vy: 0,
                r: rr,
                color: langColor('Assets'),
                meta: { 
                  delta_bytes: unknown,
                  parentId: eventId,
                  orbitRadius: satOrbit,
                  orbitAngle: a,
                  orbitSpeed: 0.2
                },
                locked: false,
              });
              addLink(ev.id, sn.id, satOrbit, 0.04);
            }
          });
        });
      }

      function applyPhysics(dt) {
        // Apply orbital rotation animations
        for (const n of nodes) {
          if (!n.meta || n.meta.orbitSpeed === undefined) continue;
          
          // Update orbit angle
          n.meta.orbitAngle += n.meta.orbitSpeed * dt;
          
          // Projects orbit around galactic center
          if (n.meta.parentId === 'galaxy') {
            const center = n.meta.galaxyCenter;
            const radius = n.meta.orbitRadius || 0;
            n.x = center.x + Math.cos(n.meta.orbitAngle) * radius;
            n.y = center.y + Math.sin(n.meta.orbitAngle) * radius;
            continue;
          }
          
          // Find parent node for events and satellites
          const parent = nodes.find(p => p.id === n.meta.parentId);
          if (!parent) continue;
          
          // Update position based on parent position + orbital rotation
          const radius = n.meta.orbitRadius || 0;
          n.x = parent.x + Math.cos(n.meta.orbitAngle) * radius;
          n.y = parent.y + Math.sin(n.meta.orbitAngle) * radius;
        }
        
        // Soft collision detection - bubbles can partially pass through each other
        // Like ethereal nebula clouds - they interact but don't hard collide
        for (let i = 0; i < nodes.length; i++) {
          for (let j = i + 1; j < nodes.length; j++) {
            const a = nodes[i];
            const b = nodes[j];
            
            // Skip locked nodes entirely
            if (a.locked && b.locked) continue;
            
            const dx = b.x - a.x;
            const dy = b.y - a.y;
            const dist = Math.sqrt(dx * dx + dy * dy);
            
            // Allow overlap - only apply force when significantly overlapping
            // Bubbles can pass through each other with just a gentle push
            const overlapThreshold = (a.r + b.r) * 0.7; // Only react at 70% overlap
            
            if (dist < overlapThreshold && dist > 0.1) {
              const overlap = overlapThreshold - dist;
              const nx = dx / dist; // Normalize
              const ny = dy / dist;
              
              // Very soft, muted separation force - like clouds drifting past each other
              const softness = 0.05; // Much gentler than before (was 0.5)
              const separationForce = overlap * softness;
              
              // Only apply to non-locked nodes
              if (!a.locked) {
                a.x -= nx * separationForce;
                a.y -= ny * separationForce;
                // Very gentle velocity change
                a.vx -= nx * separationForce * 0.02;
                a.vy -= ny * separationForce * 0.02;
              }
              if (!b.locked) {
                b.x += nx * separationForce;
                b.y += ny * separationForce;
                // Very gentle velocity change
                b.vx += nx * separationForce * 0.02;
                b.vy += ny * separationForce * 0.02;
              }
            }
          }
        }
        
        // Apply velocity and damping
        for (const n of nodes) {
          if (n.locked) continue;
          
          // Apply velocity
          n.x += n.vx * dt;
          n.y += n.vy * dt;
          
          // Higher damping for smoother, more fluid motion
          n.vx *= 0.98; // was 0.95
          n.vy *= 0.98;
        }
      }

      function nodeScreenPos(n) {
        // Apply zoom transform around viewport center
        const w = CSS_W || window.innerWidth || canvas.clientWidth || 1;
        const h = CSS_H || window.innerHeight || canvas.clientHeight || 1;
        const centerX = w * 0.5;
        const centerY = h * 0.5;
        
        const rawX = num(n.x, centerX);
        const rawY = num(n.y, centerY);
        
        // Zoom around center
        const zoomedX = centerX + (rawX - centerX) * zoomLevel;
        const zoomedY = centerY + (rawY - centerY) * zoomLevel;
        
        return {
          x: zoomedX,
          y: zoomedY,
        };
      }

      function calculateBounds() {
        // Calculate bounding box of all nodes
        if (nodes.length === 0) return { minX: 0, maxX: 1000, minY: 0, maxY: 1000 };
        
        let minX = Infinity, maxX = -Infinity;
        let minY = Infinity, maxY = -Infinity;
        
        for (const n of nodes) {
          const x = num(n.x, 0);
          const y = num(n.y, 0);
          // Use the actual clamped radius that will be displayed
          const r = clamp(num(n.r, 20), 2, 140);
          
          minX = Math.min(minX, x - r);
          maxX = Math.max(maxX, x + r);
          minY = Math.min(minY, y - r);
          maxY = Math.max(maxY, y + r);
        }
        
        return { minX, maxX, minY, maxY };
      }

      function autoFitZoom() {
        // Calculate zoom level to fit all nodes in viewport
        const bounds = calculateBounds();
        const w = CSS_W || window.innerWidth || canvas.clientWidth || 1;
        const h = CSS_H || window.innerHeight || canvas.clientHeight || 1;
        
        const contentWidth = bounds.maxX - bounds.minX;
        const contentHeight = bounds.maxY - bounds.minY;
        
        // Add 10% padding
        const scaleX = (w * 0.9) / contentWidth;
        const scaleY = (h * 0.9) / contentHeight;
        
        targetZoom = Math.min(scaleX, scaleY, ZOOM_MAX);
        targetZoom = Math.max(targetZoom, ZOOM_MIN);
      }

      function draw() {
        // Smooth zoom interpolation
        zoomLevel += (targetZoom - zoomLevel) * ZOOM_SMOOTH;
        
        // Safety: if the canvas ended up with a tiny layout box, re-measure/re-size.
        if (canvas.width < 50 || canvas.height < 50) {
          resize();
        }
        const w = CSS_W || window.innerWidth || canvas.clientWidth || 1;
        const h = CSS_H || window.innerHeight || canvas.clientHeight || 1;
        ctx.clearRect(0, 0, w, h);

        // Background stars (parallax)
        ensureStars();
        ctx.save();
        ctx.fillStyle = '#0b0c10';
        ctx.fillRect(0, 0, w, h);
        for (const s of stars) {
          const yy = s.y - scrollY() * (0.25 * s.z);
          const y = ((yy % (h + 50)) + (h + 50)) % (h + 50) - 25;
          ctx.globalAlpha = s.a;
          ctx.fillStyle = '#e7e9ee';
          ctx.beginPath();
          ctx.arc(s.x, y, s.r, 0, Math.PI * 2);
          ctx.fill();
        }
        ctx.restore();

        // Debug beacon: draw it BELOW the sticky header so it's actually visible.
        ctx.save();
        ctx.globalAlpha = 1.0;
        ctx.fillStyle = '#ffffff';
        ctx.beginPath();
        ctx.arc(20, 90, 6, 0, Math.PI * 2);
        ctx.fill();
        ctx.font = '12px system-ui, -apple-system, Segoe UI, Roboto, sans-serif';
        let drawn = 0;
        let skipped = 0;
        let badX = 0, badY = 0, badR = 0;
        ctx.restore();

        // Links - connect bubble edges, not centers
        ctx.save();
        for (const l of links) {
          const a = nodes.find(n => n.id === l.a);
          const b = nodes.find(n => n.id === l.b);
          if (!a || !b) continue;
          const ap = nodeScreenPos(a);
          const bp = nodeScreenPos(b);
          
          // Calculate vector from a to b
          const dx = bp.x - ap.x;
          const dy = bp.y - ap.y;
          const dist = Math.sqrt(dx*dx + dy*dy);
          if (dist < 0.1) continue; // Skip if nodes are at same position
          
          // Normalize and offset by bubble radii to connect at edges
          const ndx = dx / dist;
          const ndy = dy / dist;
          // Scale radii by zoom level like we do when drawing
          const ar = clamp(num(a.r, 20) * zoomLevel, 2, 140);
          const br = clamp(num(b.r, 20) * zoomLevel, 2, 140);
          
          const startX = ap.x + ndx * ar;
          const startY = ap.y + ndy * ar;
          const endX = bp.x - ndx * br;
          const endY = bp.y - ndy * br;
          
          const alpha = a.type === 'project' || b.type === 'project' ? 0.22 : 0.18;
          ctx.globalAlpha = alpha;
          ctx.strokeStyle = '#cfd6e1';
          ctx.lineWidth = 1;
          ctx.beginPath();
          ctx.moveTo(startX, startY);
          ctx.lineTo(endX, endY);
          ctx.stroke();
        }
        ctx.restore();

        // Nodes (high-contrast fallback so bubbles are unmistakable)
        hovered = null;
        const mx = mouse.x, my = mouse.y;
        const drawOrder = [...nodes].sort((a,b) => (a.z - b.z) || (a.r - b.r));
        for (const n of drawOrder) {
          const p = nodeScreenPos(n);
          // Use num() to guarantee finite fallbacks (screen center if coord is missing/invalid).
          const px = num(p.x, w * 0.5);
          const py = num(p.y, h * 0.5);
          const nr = num(n.r, 20);
          // These should NEVER fail now, but keep diagnostics just in case.
          if (!Number.isFinite(px)) badX += 1;
          if (!Number.isFinite(py)) badY += 1;
          if (!Number.isFinite(nr)) badR += 1;
          if (!Number.isFinite(px) || !Number.isFinite(py) || !Number.isFinite(nr)) {
            skipped += 1;
            continue;
          }
          // Scale radius by zoom level
          const rr = clamp(nr * zoomLevel, 2, 140);

          // Hover detection (screen coords)
          const dx = mx - p.x;
          const dy = my - p.y;
          if ((dx*dx + dy*dy) <= (rr*rr)) {
            hovered = n;
          }

          ctx.save();
          
          // Reference: galaxy with bright center, WIDE diffuse glow, NO visible edge
          const baseColor = n.color || '#7cf2c5';
          const isImportant = n.type === 'project' || n.type === 'event';
          
          // Parse base color to get RGB
          const parseColor = (hex) => {
            const r = parseInt(hex.slice(1,3), 16);
            const g = parseInt(hex.slice(3,5), 16);
            const b = parseInt(hex.slice(5,7), 16);
            return { r, g, b };
          };
          const rgb = parseColor(baseColor);
          
          // Diffuse glow - edges must be completely invisible
          const glowSize = isImportant ? rr * 2.8 : rr * 2.2;
          ctx.globalAlpha = 0.65; // Brighter like reference galaxies
          
          const unified = ctx.createRadialGradient(
            px - rr * 0.08, py - rr * 0.08, 0,
            px, py, glowSize
          );
          
          // SUPER BRIGHT center like reference galaxies - intense white glow
          if (isImportant && rr > 20) {
            // Large bubbles - INTENSE white star-like center
            unified.addColorStop(0, 'rgba(255,255,255,1.0)');
            unified.addColorStop(0.04, 'rgba(255,255,255,1.0)');
            unified.addColorStop(0.08, 'rgba(255,255,255,0.98)');
            unified.addColorStop(0.12, 'rgba(255,255,255,0.92)');
            unified.addColorStop(0.18, lightenColor(baseColor, 0.85));
            unified.addColorStop(0.26, lightenColor(baseColor, 0.65));
            unified.addColorStop(0.36, lightenColor(baseColor, 0.4));
            unified.addColorStop(0.48, lightenColor(baseColor, 0.2));
            unified.addColorStop(0.62, baseColor);
            unified.addColorStop(0.74, `rgba(${rgb.r},${rgb.g},${rgb.b},0.85)`);
            unified.addColorStop(0.83, `rgba(${rgb.r},${rgb.g},${rgb.b},0.65)`);
            unified.addColorStop(0.90, `rgba(${rgb.r},${rgb.g},${rgb.b},0.42)`);
            unified.addColorStop(0.94, `rgba(${rgb.r},${rgb.g},${rgb.b},0.24)`);
            unified.addColorStop(0.97, `rgba(${rgb.r},${rgb.g},${rgb.b},0.12)`);
            unified.addColorStop(0.98, `rgba(${rgb.r},${rgb.g},${rgb.b},0.06)`);
            unified.addColorStop(0.99, `rgba(${rgb.r},${rgb.g},${rgb.b},0.02)`);
            unified.addColorStop(0.995, `rgba(${rgb.r},${rgb.g},${rgb.b},0.006)`);
            unified.addColorStop(0.998, `rgba(${rgb.r},${rgb.g},${rgb.b},0.001)`);
            unified.addColorStop(1, `rgba(${rgb.r},${rgb.g},${rgb.b},0)`);
          } else {
            // Smaller satellites - BRIGHT white center, fast fade to wispy
            unified.addColorStop(0, 'rgba(255,255,255,1.0)');
            unified.addColorStop(0.04, 'rgba(255,255,255,0.95)');
            unified.addColorStop(0.08, 'rgba(255,255,255,0.85)');
            unified.addColorStop(0.14, lightenColor(baseColor, 0.65));
            unified.addColorStop(0.22, lightenColor(baseColor, 0.4));
            unified.addColorStop(0.32, lightenColor(baseColor, 0.15));
            unified.addColorStop(0.45, baseColor);
            unified.addColorStop(0.58, `rgba(${rgb.r},${rgb.g},${rgb.b},0.65)`);
            unified.addColorStop(0.70, `rgba(${rgb.r},${rgb.g},${rgb.b},0.40)`);
            unified.addColorStop(0.80, `rgba(${rgb.r},${rgb.g},${rgb.b},0.20)`);
            unified.addColorStop(0.88, `rgba(${rgb.r},${rgb.g},${rgb.b},0.09)`);
            unified.addColorStop(0.94, `rgba(${rgb.r},${rgb.g},${rgb.b},0.03)`);
            unified.addColorStop(0.98, `rgba(${rgb.r},${rgb.g},${rgb.b},0.008)`);
            unified.addColorStop(0.995, `rgba(${rgb.r},${rgb.g},${rgb.b},0.002)`);
            unified.addColorStop(1, `rgba(${rgb.r},${rgb.g},${rgb.b},0)`);
          }
          
          ctx.fillStyle = unified;
          ctx.beginPath();
          ctx.arc(px, py, glowSize, 0, Math.PI * 2);
          ctx.fill();
          
          ctx.restore();
          drawn += 1;
        }

        // Debug text after drawing attempt
        ctx.save();
        ctx.globalAlpha = 1.0;
        ctx.fillStyle = '#ffffff';
        ctx.font = '12px system-ui, -apple-system, Segoe UI, Roboto, sans-serif';
        ctx.fillText(
          `draw() nodes=${nodes.length} drawn=${drawn} skipped=${skipped} canvas=${w}x${h}`,
          34,
          94
        );
        ctx.restore();

        // Tooltip
        if (hovered) {
          tooltip.style.display = 'block';
          const n = hovered;
          if (n.type === 'project') {
            tooltip.innerHTML = `<div><span class="badge">Project</span>${n.label}</div>`;
          } else if (n.type === 'event') {
            const e = (n.meta && n.meta.event) ? n.meta.event : {};
            tooltip.innerHTML = `
              <div><span class="badge">Event</span>${String(e.event_id || '')}</div>
              <div>net_loc=${e.net_loc_estimate}, churn_loc=${e.churn_loc_estimate}, delta_bytes=${e.total_delta_bytes}</div>
              <div>files +${e.counts.files_added} ~${e.counts.files_modified} -${e.counts.files_removed}</div>
            `;
          } else {
            tooltip.innerHTML = `<div><span class="badge">Type</span>${n.label}</div><div>delta_bytes=${fmt(Number(n.meta?.delta_bytes||0))}</div>`;
          }
          tooltip.style.left = (mouse.x + 14) + 'px';
          tooltip.style.top = (mouse.y + 14) + 'px';
        } else {
          tooltip.style.display = 'none';
        }
      }

      function frame(now) {
        const dt = clamp((now - lastT) / 1000, 0.01, 0.05);
        lastT = now;
        applyPhysics(dt);
        draw();
        requestAnimationFrame(frame);
      }

      async function loadEvents() {
        const res = await fetch('./events.json', { cache: 'no-store' });
        if (!res.ok) throw new Error('Failed to load events.json');
        return await res.json();
      }

      async function main() {
        try {
          // Ensure canvas size is correct before building/laying out nodes.
          resize();
          ensureStars();
          const events = await loadEvents();
          buildScene(events);
          
          // Auto-fit zoom to show all nodes
          autoFitZoom();
        } catch (e) {
          countEl.textContent = String(e);
        }
      }

      function wire() {
        window.addEventListener('resize', resize);
        
        document.getElementById('reload').addEventListener('click', main);
        
        // Zoom controls
        document.getElementById('zoom-in').addEventListener('click', () => {
          targetZoom = Math.min(targetZoom + ZOOM_STEP, ZOOM_MAX);
        });
        
        document.getElementById('zoom-out').addEventListener('click', () => {
          targetZoom = Math.max(targetZoom - ZOOM_STEP, ZOOM_MIN);
        });
        
        document.getElementById('zoom-reset').addEventListener('click', () => {
          autoFitZoom();
        });
        
        // Mouse wheel zoom
        canvas.addEventListener('wheel', (e) => {
          e.preventDefault();
          const delta = -Math.sign(e.deltaY) * ZOOM_STEP;
          targetZoom = clamp(targetZoom + delta, ZOOM_MIN, ZOOM_MAX);
        }, { passive: false });
        
        window.addEventListener('mousemove', (e) => { mouse.x = e.clientX; mouse.y = e.clientY; });
        window.addEventListener('scroll', () => { /* parallax uses scrollY() */ });
      }
      resize();
      ensureStars();
      wire();
      // Wait one frame so layout is stable before building the scene.
      requestAnimationFrame(main);
      requestAnimationFrame(frame);
    </script>
  </body>
</html>
"""
    html = html.replace("__VIZ_VERSION__", str(viz_version))
    # Write local viz copy
    _atomic_write_text(index_path, html)
    if not events_path.exists():
        _atomic_write_json(events_path, [])

    # Write GitHub Pages copy (docs/ root). Also add .nojekyll for safety.
    _atomic_write_text(pages_index_path, html)
    if not pages_events_path.exists():
        _atomic_write_json(pages_events_path, [])
    nojekyll = (repo_path / PAGES_DIRNAME) / ".nojekyll"
    if not nojekyll.exists():
        _atomic_write_text(nojekyll, "")

    return pages_index_path


def append_event(repo_path: Path, event_payload: dict) -> Path:
    _ = ensure_viz_index_html(repo_path)
    _, events_path = viz_paths(repo_path)
    _, pages_events_path = pages_paths(repo_path)

    events: list[dict]
    if events_path.exists():
        events = json.loads(events_path.read_text(encoding="utf-8"))
        if not isinstance(events, list):
            events = []
    else:
        events = []

    # Avoid duplicates by event_id.
    event_id = event_payload.get("event_id")
    if event_id and any(e.get("event_id") == event_id for e in events):
        # Keep docs/ in sync even if local already had it.
        if pages_events_path.exists():
            _atomic_write_json(pages_events_path, events)
        return pages_events_path

    events.append(event_payload)
    # Keep chronological order by event_id (ISO timestamps)
    events.sort(key=lambda e: str(e.get("event_id", "")))
    _atomic_write_json(events_path, events)
    _atomic_write_json(pages_events_path, events)
    return pages_events_path


