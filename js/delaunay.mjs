// Voronoi cells and Delaunay triangles with d3-delaunay.
// stdin:  {points: [[x, y]], bounds: [x, y, w, h] | null, kind: "voronoi"|"delaunay"}
// stdout: {cells: [[[x, y], ...], ...]} (closed polygons, first point repeated)
import { Delaunay } from 'd3-delaunay';
import { readFileSync } from 'node:fs';

const raw = readFileSync(0, 'utf8');
const { points, bounds = null, kind = 'voronoi' } = JSON.parse(raw || '{}');
if (!Array.isArray(points) || points.length < 3) {
  throw new Error('delaunay.mjs needs 3+ points');
}
const delaunay = Delaunay.from(points);
let cells;
if (kind === 'voronoi') {
  const [x, y, w, h] = bounds ?? [0, 0, 1000, 1000];
  const voronoi = delaunay.voronoi([x, y, x + w, y + h]);
  cells = [...voronoi.cellPolygons()].map((poly) => poly.map(([px, py]) => [px, py]));
} else if (kind === 'delaunay') {
  const { triangles } = delaunay;
  cells = [];
  for (let i = 0; i < triangles.length; i += 3) {
    cells.push([points[triangles[i]], points[triangles[i + 1]], points[triangles[i + 2]],
                points[triangles[i]]]);
  }
} else {
  throw new Error(`delaunay.mjs kind is ${JSON.stringify(kind)}, want "voronoi" or "delaunay"`);
}
if (!cells.length) throw new Error(`${kind} produced no cells`);
console.log(JSON.stringify({ cells }));
