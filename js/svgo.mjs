/** Optimize an SVG with SVGO. Reads stdin {input, output}; prints result JSON last. */
import { readFileSync, writeFileSync } from 'node:fs';
import { optimize } from 'svgo';

const { input, output } = JSON.parse(readFileSync(0, 'utf8'));
const svg = readFileSync(input, 'utf8');
const result = optimize(svg, { path: input, multipass: true });
if (result.error) throw new Error(`svgo: ${result.error}`);
writeFileSync(output, result.data);
writeFileSync(1, JSON.stringify({
  ok: true, output, bytes_in: svg.length, bytes_out: result.data.length,
}) + '\n');
