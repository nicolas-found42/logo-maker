// Pressure-sensitive freehand outline with perfect-freehand.
// stdin:  {points: [[x, y, pressure?]], size, thinning, smoothing, streamline}
// stdout: {outline: [[x, y], ...]} (closed polygon; repeat first point at the end)
import { getStroke } from 'perfect-freehand';
import { readFileSync } from 'node:fs';

const raw = readFileSync(0, 'utf8');
const { points, size = 16, thinning = 0.5, smoothing = 0.5, streamline = 0.5 } = JSON.parse(raw || '{}');
if (!Array.isArray(points) || points.length < 2) throw new Error('freehand.mjs needs 2+ points');
const outline = getStroke(points, { size, thinning, smoothing, streamline });
if (!outline.length) throw new Error('perfect-freehand returned no outline');
console.log(JSON.stringify({ outline }));
