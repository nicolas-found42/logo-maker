// Low-poly triangle fields with trianglify. Only the pattern data (points/polys)
// is used to build paths; nothing touches the DOM.
// stdin:  {width, height, cellSize, variance, seed, xColors?, yColors?}
// stdout: {triangles: [{pts: [[x, y] x3], fill: "#rrggbb"}]}
import trianglify from 'trianglify';
import { readFileSync } from 'node:fs';

const raw = readFileSync(0, 'utf8');
const { width, height, cellSize = 48, variance = 0.75, seed = '0',
        xColors = 'random', yColors = 'match' } = JSON.parse(raw || '{}');
const pattern = trianglify({ width, height, cellSize, variance, seed,
                             xColors, yColors });
const triangles = pattern.polys.map((poly) => ({
  pts: poly.vertexIndices.map((vi) => pattern.points[vi]),
  fill: poly.color.hex(),
}));
console.log(JSON.stringify({ triangles }));
