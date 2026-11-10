/** App-icon set via pwa-asset-generator (it drives Chrome itself).
 * Reads stdin {source, out_dir, manifest, background, opaque};
 * prints result JSON last. The manifest path is created/updated in place.
 */
import { existsSync, mkdirSync, readdirSync, readFileSync, writeFileSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.dirname(fileURLToPath(import.meta.url));
const { source, out_dir, manifest, background, opaque } = JSON.parse(readFileSync(0, 'utf8'));
mkdirSync(out_dir, { recursive: true });
const bin = path.join(root, 'node_modules', '.bin', 'pwa-asset-generator');
if (manifest && !existsSync(manifest)) writeFileSync(manifest, '{}\n');
const args = [
  source, out_dir,
  '--icon-only', '--favicon', '--type', 'png',
  '--background', background ?? 'transparent',
  '--opaque', String(opaque ?? false),
  '--padding', '10%',
  '--log', 'false',
];
if (manifest) args.push('--manifest', manifest);
const proc = spawnSync(bin, args, { encoding: 'utf8' });
if (proc.error) throw new Error(`pwa-asset-generator not runnable: ${proc.error.message}`);
if (proc.status !== 0) {
  throw new Error(`pwa-asset-generator failed: ${(proc.stderr || proc.stdout || '').slice(-2000)}`);
}
writeFileSync(1, JSON.stringify({
  ok: true, out_dir, files: readdirSync(out_dir).sort(),
}) + '\n');
