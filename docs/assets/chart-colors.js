/* Ported from college-football-index js/chart-colors.js. */
/**
 * Solid chart colors, calculated from the colors actually displayed (8-bit sRGB).
 *
 * Conversion matrices and Euclidean OKLab distance (Delta E OK):
 * https://www.w3.org/TR/css-color-4/#color-conversion-code
 * Luminance and contrast ratio:
 * https://www.w3.org/TR/WCAG22/#dfn-relative-luminance
 * https://www.w3.org/TR/WCAG22/#dfn-contrast-ratio
 *
 * Divider selection maximizes the smaller OKLab distance to its two neighbors
 * among a finite set of sRGB candidates meeting 3:1 contrast against both.
 * This is a candidate search, not a continuous global maximum or a claim of
 * complete accessibility. If no sampled candidate meets both contrast targets,
 * the search prioritizes the best minimum contrast, then perceptual distance.
 */

const DIVIDER_CONTRAST = 3;
// These secondary-color thresholds are visual heuristics, not WCAG criteria.
const SECONDARY_CONTRAST = 2;
const SECONDARY_DISTANCE = 0.18;
const EPSILON = 1e-12;
const DEFAULT_PRIMARY = [37, 91, 122];

const colorCache = new Map();
const dividerCache = new Map();
const paletteCache = new Map();
let dividerCandidates;

function remember(cache, key, value, limit) {
  if (cache.size >= limit) cache.delete(cache.keys().next().value);
  cache.set(key, value);
  return value;
}

function multiply(matrix, vector) {
  return matrix.map(row => row[0] * vector[0] + row[1] * vector[1] + row[2] * vector[2]);
}

function linearChannel(channel) {
  const value = channel / 255;
  return value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4;
}

function encodedChannel(value) {
  return value <= 0.0031308 ? 12.92 * value : 1.055 * value ** (1 / 2.4) - 0.055;
}

const RGB_TO_XYZ = [
  [506752 / 1228815, 87881 / 245763, 12673 / 70218],
  [87098 / 409605, 175762 / 245763, 12673 / 175545],
  [7918 / 409605, 87881 / 737289, 1001167 / 1053270],
];
const XYZ_TO_LMS = [
  [0.8190224379967030, 0.3619062600528904, -0.1288737815209879],
  [0.0329836539323885, 0.9292868615863434, 0.0361446663506424],
  [0.0481771893596242, 0.2642395317527308, 0.6335478284694309],
];
const LMS_TO_LAB = [
  [0.2104542683093140, 0.7936177747023054, -0.0040720430116193],
  [1.9779985324311684, -2.4285922420485799, 0.4505937096174110],
  [0.0259040424655478, 0.7827717124575296, -0.8086757549230774],
];
const LAB_TO_LMS = [
  [1, 0.3963377773761749, 0.2158037573099136],
  [1, -0.1055613458156586, -0.0638541728258133],
  [1, -0.0894841775298119, -1.2914855480194092],
];
const LMS_TO_XYZ = [
  [1.2268798758459243, -0.5578149944602171, 0.2813910456659647],
  [-0.0405757452148008, 1.1122868032803170, -0.0717110580655164],
  [-0.0763729366746601, -0.4214933324022432, 1.5869240198367816],
];
const XYZ_TO_RGB = [
  [12831 / 3959, -329 / 214, -1974 / 3959],
  [-851781 / 878810, 1648619 / 878810, 36519 / 878810],
  [705 / 12673, -2585 / 12673, 705 / 667],
];

function colorRecord(channels) {
  const rgb = channels.map(value => Math.round(Math.max(0, Math.min(255, value))));
  const key = rgb.join(',');
  if (colorCache.has(key)) return colorCache.get(key);
  const linear = rgb.map(linearChannel);
  const xyz = multiply(RGB_TO_XYZ, linear);
  const lab = multiply(LMS_TO_LAB, multiply(XYZ_TO_LMS, xyz).map(Math.cbrt));
  return remember(colorCache, key, {
    key,
    css: `rgb(${rgb.join(', ')})`,
    lab,
    luminance: 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2],
  }, 4096);
}

// Accept provider hex, comma-separated RGB, and the rgb() strings returned here.
// Invalid values never enter CSS; callers get a stable neutral fallback instead.
function parseColor(value, fallback = null) {
  if (typeof value === 'string') {
    const text = value.trim();
    const hex = /^#?([\da-f]{3}|[\da-f]{6})$/i.exec(text);
    if (hex) {
      const expanded = hex[1].length === 3
        ? [...hex[1]].map(character => character + character).join('')
        : hex[1];
      return colorRecord([0, 2, 4].map(offset => parseInt(expanded.slice(offset, offset + 2), 16)));
    }
    const parts = (text.match(/^rgb\((.*)\)$/i)?.[1] ?? text).split(',').map(part => part.trim());
    const number = /^[+-]?(?:\d+(?:\.\d*)?|\.\d+)$/;
    if (parts.length === 3 && parts.every(part => number.test(part) && Number.isFinite(Number(part)))) {
      return colorRecord(parts.map(Number));
    }
  }
  return fallback ? colorRecord(fallback) : null;
}

function contrast(left, right) {
  return (Math.max(left.luminance, right.luminance) + 0.05)
    / (Math.min(left.luminance, right.luminance) + 0.05);
}

function distanceSquared(left, right) {
  return left.lab.reduce((sum, value, index) => sum + (value - right.lab[index]) ** 2, 0);
}

function lchLinearRgb(lightness, chroma, hue) {
  const lab = [lightness, chroma * Math.cos(hue), chroma * Math.sin(hue)];
  const lms = multiply(LAB_TO_LMS, lab).map(value => value ** 3);
  return multiply(XYZ_TO_RGB, multiply(LMS_TO_XYZ, lms));
}

function inGamut(channels) {
  return channels.every(value => value >= -EPSILON && value <= 1 + EPSILON);
}

// Reduce chroma at a fixed OKLCH hue/lightness until the color fits sRGB.
// This deliberately simple gamut mapping keeps derived rushing shades on-brand.
function lchColor(lightness, chroma, hue) {
  let linear = lchLinearRgb(lightness, chroma, hue);
  if (!inGamut(linear)) {
    let low = 0;
    let high = chroma;
    for (let step = 0; step < 16; step += 1) {
      const middle = (low + high) / 2;
      if (inGamut(lchLinearRgb(lightness, middle, hue))) low = middle;
      else high = middle;
    }
    linear = lchLinearRgb(lightness, low, hue);
  }
  return colorRecord(linear.map(value => 255 * encodedChannel(Math.max(0, Math.min(1, value)))));
}

function candidates() {
  if (dividerCandidates) return dividerCandidates;
  const unique = new Map();
  const add = record => unique.set(record.key, record);
  const levels = [0, 32, 64, 96, 128, 160, 192, 224, 255];
  for (const red of levels) for (const green of levels) for (const blue of levels) {
    add(colorRecord([red, green, blue]));
  }
  // Dense neutrals plus perceptually spaced hue/lightness samples supplement
  // the RGB grid, including candidates near the sRGB gamut boundary.
  for (let gray = 0; gray <= 255; gray += 1) add(colorRecord([gray, gray, gray]));
  for (const lightness of [0.15, 0.25, 0.35, 0.45, 0.55, 0.65, 0.75, 0.85, 0.95]) {
    for (const chroma of [0.08, 0.16, 0.24, 0.32]) {
      for (let hue = 0; hue < 360; hue += 15) {
        add(lchColor(lightness, chroma, hue * Math.PI / 180));
      }
    }
  }
  dividerCandidates = [...unique.values()];
  return dividerCandidates;
}

/** A deterministic, symmetric separator calculated from both adjacent fills. */
function barDividerColor(left, right) {
  const first = parseColor(left, DEFAULT_PRIMARY);
  const second = parseColor(right, DEFAULT_PRIMARY);
  const key = [first.key, second.key].sort().join('|');
  if (dividerCache.has(key)) return dividerCache.get(key);
  let feasible;
  let fallback;
  for (const candidate of candidates()) {
    const minimumContrast = Math.min(contrast(candidate, first), contrast(candidate, second));
    const minimumDistance = Math.min(distanceSquared(candidate, first), distanceSquared(candidate, second));
    const choice = { candidate, minimumContrast, minimumDistance };
    if (!fallback || minimumContrast > fallback.minimumContrast + EPSILON
      || (Math.abs(minimumContrast - fallback.minimumContrast) <= EPSILON
        && minimumDistance > fallback.minimumDistance + EPSILON)) fallback = choice;
    if (minimumContrast >= DIVIDER_CONTRAST && (!feasible
      || minimumDistance > feasible.minimumDistance + EPSILON
      || (Math.abs(minimumDistance - feasible.minimumDistance) <= EPSILON
        && minimumContrast > feasible.minimumContrast + EPSILON))) feasible = choice;
  }
  return remember(dividerCache, key, (feasible ?? fallback).candidate.css, 2048);
}

function derivedRushing(primary) {
  const [, a, b] = primary.lab;
  const chroma = Math.hypot(a, b);
  const hue = chroma < 0.00001 ? 0 : Math.atan2(b, a);
  const targetLightness = primary.lab[0] < 0.55 ? 0.78 : 0.25;
  const lightnesses = [targetLightness, 0.08, 0.15, 0.25, 0.35, 0.45, 0.55, 0.65, 0.75, 0.85, 0.95];
  let preferred;
  let fallback;
  for (const lightness of lightnesses) {
    const candidate = lchColor(lightness, chroma, hue);
    const ratio = contrast(primary, candidate);
    const distance = distanceSquared(primary, candidate);
    const targetDistance = Math.abs(lightness - targetLightness);
    if (!fallback || ratio > fallback.ratio + EPSILON
      || (Math.abs(ratio - fallback.ratio) <= EPSILON && distance > fallback.distance)) {
      fallback = { candidate, ratio, distance };
    }
    if (ratio >= DIVIDER_CONTRAST && distance >= SECONDARY_DISTANCE ** 2
      && (!preferred || targetDistance < preferred.targetDistance - EPSILON
        || (Math.abs(targetDistance - preferred.targetDistance) <= EPSILON && ratio > preferred.ratio))) {
      preferred = { candidate, targetDistance, ratio };
    }
  }
  return (preferred ?? fallback).candidate;
}

function textInk(fill) {
  const dark = colorRecord([0, 0, 0]);
  const light = colorRecord([255, 255, 255]);
  return contrast(fill, dark) >= contrast(fill, light) ? dark.css : light.css;
}

/** Team-primary passing fill, distinct rushing fill, calculated divider and ink. */
function yardageBarColors(primary, secondary) {
  const passing = parseColor(primary, DEFAULT_PRIMARY);
  const alternate = parseColor(secondary);
  const key = `${passing.key}|${alternate?.key ?? ''}`;
  if (paletteCache.has(key)) return paletteCache.get(key);
  const rushing = alternate && contrast(passing, alternate) >= SECONDARY_CONTRAST
    && distanceSquared(passing, alternate) >= SECONDARY_DISTANCE ** 2
    ? alternate : derivedRushing(passing);
  return remember(paletteCache, key, Object.freeze({
    passing: passing.css,
    rushing: rushing.css,
    divider: barDividerColor(passing.css, rushing.css),
    passingInk: textInk(passing),
    rushingInk: textInk(rushing),
  }), 512);
}

var NFLChartColorsRoot = typeof window !== "undefined" ? window : globalThis;
NFLChartColorsRoot.NFLChartColors = {
  barDividerColor: barDividerColor,
  yardageBarColors: yardageBarColors
};
