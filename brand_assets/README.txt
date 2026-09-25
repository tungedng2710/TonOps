BRAND ASSET PACK
================

This package contains production files for the approved brain + geometric technology logo mark.

IMPORTANT
- The logo background has been removed. SVG masters and all files under png/ are transparent.
- app-icon-slate.svg / app-icon-slate-*.png intentionally contain a slate background because app icons require a bounded surface.
- SVG is the master format. Use SVG whenever possible for web, print, signage, Figma, Illustrator, Affinity Designer, or Inkscape.

FILES
- svg/logo-mark-black.svg      Tight black vector master, transparent background
- svg/logo-mark-white.svg      Tight white/reversed vector master, transparent background
- svg/logo-mark-slate.svg      Slate vector master, transparent background
- svg/logo-icon-black.svg      Square padded icon master, transparent background
- svg/logo-icon-white.svg      Square padded reversed icon master, transparent background
- png/black/*                  Transparent black PNG exports from 16 to 2048 px
- png/white/*                  Transparent white PNG exports from 16 to 2048 px
- icons/favicon.svg            Rounded white favicon vector
- icons/favicon.ico            Multi-size favicon
- icons/favicon-*.png          Common favicon / touch icon sizes
- icons/app-icon-slate.*       Optional white-on-slate app icon
- spec/brand-colors.json       Brand palette tokens
- spec/brand-colors.css        CSS variables
- spec/logo-spec.json          Geometry / clear-space recommendations

USAGE
1. Prefer logo-mark-*.svg for production.
2. Use black on light backgrounds and white on dark backgrounds.
3. Keep at least 10% of the logo width as clear space around the mark.
4. Avoid stretching, skewing, outlining, adding drop shadows, or changing individual internal components.
5. For very small UI sizes, use the square logo-icon SVG/PNG versions.

SOURCE
The vector master was reconstructed from the approved final logo concept rather than shipping the raster white background.
