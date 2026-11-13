/**
 * Remark plugin: replaces the version token %INVENTAG_VERSION% in the docs.
 *
 * Write %INVENTAG_VERSION% where a page names the current release, for example
 * `pip install inventag-aws==%INVENTAG_VERSION%` or `git checkout v%INVENTAG_VERSION%`.
 * It works in text, inline code, fenced code blocks (and their title="..."),
 * link and image URLs, raw HTML in .md pages and string attributes of MDX
 * elements, in .md and .mdx, in English and the translations.
 *
 *   docs/ and the translated copies   -> the version in ../version.json
 *   versioned_docs/version-X.Y.Z/     -> X.Y.Z (snapshots are normally stamped
 *                                        with a literal version already, see
 *                                        scripts/stamp-doc-version.mjs)
 *
 * The token is replaced before the HTML is written, so the page, the search
 * index and the code block "copy" button all see the version number.
 * Front matter is not Markdown and is not replaced: the build stops if a
 * page's front matter contains the token. Keep it out of headings too: the
 * heading anchor would change with every release.
 */
import {readFileSync} from 'node:fs';
import {fileURLToPath} from 'node:url';

export const VERSION_TOKEN = '%INVENTAG_VERSION%';

const versionFile = fileURLToPath(new URL('../../../version.json', import.meta.url));
const CURRENT_VERSION = JSON.parse(readFileSync(versionFile, 'utf8')).version;
if (!/^\d+\.\d+\.\d+$/.test(CURRENT_VERSION)) {
  throw new Error(`version-token: unexpected version "${CURRENT_VERSION}" in ${versionFile}`);
}

function versionFor(filePath) {
  const m = /[\\/]versioned_docs[\\/]version-(\d+\.\d+\.\d+)[\\/]/.exec(filePath ?? '');
  return m ? m[1] : CURRENT_VERSION;
}

// Nodes whose value is page text. MDX expressions ({...}) are JavaScript and are left alone.
const VALUE_NODES = new Set(['text', 'inlineCode', 'code', 'html']);

function replaceIn(node, version) {
  if (node.type === 'yaml' || node.type === 'toml') return; // front matter, parsed separately
  const swap = (s) => (typeof s === 'string' && s.includes(VERSION_TOKEN) ? s.split(VERSION_TOKEN).join(version) : s);
  if (VALUE_NODES.has(node.type)) node.value = swap(node.value);
  if ('url' in node) node.url = swap(node.url); // link, image, definition
  if ('meta' in node) node.meta = swap(node.meta); // ```bash title="..."
  if ('title' in node) node.title = swap(node.title);
  if (Array.isArray(node.attributes)) {
    for (const attr of node.attributes) {
      if (attr && typeof attr.value === 'string') attr.value = swap(attr.value);
    }
  }
  if (Array.isArray(node.children)) for (const child of node.children) replaceIn(child, version);
}

export default function remarkVersionToken() {
  return (tree, file) => {
    if (JSON.stringify(file.data?.frontMatter ?? {}).includes(VERSION_TOKEN)) {
      throw new Error(`${file.path}: ${VERSION_TOKEN} is not replaced in front matter; write it in the page body.`);
    }
    replaceIn(tree, versionFor(file.path));
  };
}
