# Client TODO

This directory is scaffolded for the Astro client.

TODO:
- Initialize Astro project structure.
- Add React islands and routing pages.
- Wire client API access to the indexer.



Logo SVG:

Simple: 
<svg
  width="200"
  height="200"
  viewBox="0 0 200 200"
  xmlns="http://www.w3.org/2000/svg"
>
  <!-- Extruder head -->
  <rect
    x="70"
    y="40"
    width="60"
    height="50"
    rx="12"
    ry="12"
    fill="none"
    stroke="black"
    stroke-width="5"
  />

  <!-- V-shaped nozzle (mint green fill) -->
  <path
    d="M92 97 L100 104 L108 97 Z"
    fill="#4ADE80"
    stroke="#4ADE80"
    stroke-width="5"
    stroke-linecap="round"
    stroke-linejoin="round"
  />

  <!-- Network edges (y - 3) -->
  <line x1="100" y1="121" x2="80" y2="146"
        stroke="black" stroke-width="4" stroke-linecap="round" />
  <line x1="100" y1="121" x2="120" y2="146"
        stroke="black" stroke-width="4" stroke-linecap="round" />
  <line x1="80"  y1="146" x2="120" y2="146"
        stroke="black" stroke-width="5" stroke-linecap="round" />

  <!-- Perspective ellipses (y - 3) -->
  <ellipse cx="100" cy="121" rx="9" ry="5"
           fill="white" stroke="black" stroke-width="3.5" />
  <ellipse cx="80"  cy="146" rx="9" ry="5"
           fill="white" stroke="black" stroke-width="4" />
  <ellipse cx="120" cy="146" rx="9" ry="5"
           fill="white" stroke="black" stroke-width="4" />
</svg>