// Voxel scenes with heerich, returned as SVG polygons (fills only, no strokes).
// stdin:  {tile, ops: [{type: "box"|"sphere"|"line"|"fill", position?, size?, center?,
//                       radius?, from?, to?, bounds?, test?, style?}], smooth?}
// stdout: {svg} — parse the <polygon>/<path> fills on the Python side.
import { Heerich } from 'heerich';
import { readFileSync } from 'node:fs';

const raw = readFileSync(0, 'utf8');
const { tile = 24, ops = [], smooth = false } = JSON.parse(raw || '{}');
if (!Array.isArray(ops) || !ops.length) throw new Error('heerich.mjs needs 1+ ops');
const scene = new Heerich({ tile });
for (const op of ops) {
  if (op.type === 'fill' && typeof op.test === 'string') {
    // Named solidity tests keep the JSON boundary serializable; the scene stays explicit.
    const tests = {
      ball: (x, y, z, r) => x * x + y * y + z * z <= r * r,
      column: (x, y, z, w, h) => Math.abs(x) <= w && Math.abs(y) <= w && z >= 0 && z < h,
    };
    const [name, ...args] = op.test.split(':');
    if (!tests[name]) throw new Error(`heerich.mjs unknown test ${JSON.stringify(op.test)}`);
    scene.applyGeometry({ ...op, test: (x, y, z) => tests[name](x, y, z, ...args.map(Number)) });
  } else {
    scene.applyGeometry(op);
  }
}
if (smooth) scene.smooth();
console.log(JSON.stringify({ svg: scene.toSVG() }));
