/** Draco-compress a glb with @gltf-transform + draco3dgltf.
 * Reads stdin {input, output, compression_level}; prints result JSON last.
 */
import { readFileSync, writeFileSync } from 'node:fs';
import { NodeIO } from '@gltf-transform/core';
import { ALL_EXTENSIONS } from '@gltf-transform/extensions';
import { draco, dedup, prune } from '@gltf-transform/functions';
import draco3d from 'draco3dgltf';

const { input, output, compression_level } = JSON.parse(readFileSync(0, 'utf8'));
const io = new NodeIO()
  .registerExtensions(ALL_EXTENSIONS)
  .registerDependencies({
    'draco3d.decoder': await draco3d.createDecoderModule(),
    'draco3d.encoder': await draco3d.createEncoderModule(),
  });
const doc = await io.read(input);
await doc.transform(
  dedup(),
  prune({ keepAttributes: true }),
  draco({ compressionLevel: compression_level ?? 7 }),
);
await io.write(output, doc);
const { statSync } = await import('node:fs');
writeFileSync(1, JSON.stringify({
  ok: true, output,
  bytes_in: statSync(input).size,
  bytes_out: statSync(output).size,
}) + '\n');
