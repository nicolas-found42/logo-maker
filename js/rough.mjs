// Sketchy path rendering with rough.js (no DOM needed: the generator emits op sets).
// stdin:  {d, seed, roughness, bowing, strokeWidth, fill, fillStyle}
// stdout: {sets: [{kind: "stroke"|"fill", d}]} where "stroke" sets are centerlines
//         to outline to fills and "fill" sets are already closed fills.
import rough from 'roughjs/bundled/rough.esm.js';
import { readFileSync } from 'node:fs';

function opsToD(ops) {
  let d = '';
  for (const op of ops) {
    if (op.op === 'move') {
      d += `M${op.data[0].toFixed(2)} ${op.data[1].toFixed(2)}`;
    } else if (op.op === 'lineTo') {
      d += `L${op.data[0].toFixed(2)} ${op.data[1].toFixed(2)}`;
    } else if (op.op === 'bcurveTo') {
      d += `C${op.data.map((v) => v.toFixed(2)).join(' ')}`;
    } else {
      throw new Error(`rough.js emitted an unsupported op ${JSON.stringify(op.op)}`);
    }
  }
  return d;
}

const raw = readFileSync(0, 'utf8');
const { d, seed = 0, roughness = 1.5, bowing = 1.0, strokeWidth = 2,
        fill = '#1A1A1A', fillStyle = 'solid' } = JSON.parse(raw || '{}');
if (typeof d !== 'string' || !d) throw new Error('rough.mjs needs a path d string');
const gen = rough.generator({ seed });
const drawable = gen.path(d, { roughness, bowing, strokeWidth, fill, fillStyle });
const sets = drawable.sets.map((s) => ({
  kind: s.type === 'path' ? 'stroke' : 'fill',
  d: opsToD(s.ops),
}));
console.log(JSON.stringify({ sets }));
