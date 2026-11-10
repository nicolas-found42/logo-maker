/** Installability + tile meta via the favicons library.
 * Reads stdin {source, out_dir, app_name, background, theme_color, manifest_name};
 * generates the android (manifest icons) and windows (browserconfig tiles) sets
 * from the source PNG, writes images + manifest.webmanifest + browserconfig.xml
 * into out_dir, and prints result JSON last. The core favicon sizes stay
 * hand-rolled from the flat motif (see logo_maker.export); this adds only the
 * sets the library does well (padded manifest icons, ms tiles + tile XML).
 */
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import favicons from 'favicons';

const { source, out_dir, app_name, background, theme_color, manifest_name } = JSON.parse(
  readFileSync(0, 'utf8'));
const response = await favicons(source, {
  appName: app_name,
  appShortName: app_name,
  background,
  themeColor: theme_color,
  theme_color,
  manifestMaskable: true,
  icons: {
    android: true, appleIcon: false, appleStartup: false, coast: false,
    favicons: false, firefox: false, windows: true, yandex: false,
  },
  output: { images: true, files: true, html: false },
});
mkdirSync(out_dir, { recursive: true });
const written = [];
for (const image of response.images) {
  writeFileSync(path.join(out_dir, image.name), image.contents);
  written.push(image.name);
}
for (const file of response.files) {
  let contents = file.contents;
  if ((file.name === 'manifest.webmanifest' || file.name === 'site.webmanifest')
      && manifest_name && file.name !== manifest_name) {
    continue;
  }
  if (manifest_name && (file.name === 'manifest.webmanifest' || file.name === 'site.webmanifest')) {
    const dest = path.join(out_dir, manifest_name);
    writeFileSync(dest, contents);
    written.push(manifest_name);
  } else {
    writeFileSync(path.join(out_dir, file.name), contents);
    written.push(file.name);
  }
}
writeFileSync(1, JSON.stringify({ ok: true, out_dir, files: written }) + '\n');
