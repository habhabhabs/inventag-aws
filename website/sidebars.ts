import type {SidebarsConfig} from '@docusaurus/plugin-content-docs';
// sidebars.js stays the single source of truth for navigation (CI validates
// it with `require('./sidebars.js')`). This file only adjusts presentation:
// it drops the leading emoji from category labels so the sidebar reads as a
// plain, typographic table of contents.
import source from './sidebars.js';

const EMOJI_PREFIX = /^[\p{Extended_Pictographic}️‍\s]+/u;

function clean(item: unknown): unknown {
  if (Array.isArray(item)) return item.map(clean);
  if (item && typeof item === 'object') {
    const out: Record<string, unknown> = {...(item as Record<string, unknown>)};
    if (typeof out.label === 'string') out.label = out.label.replace(EMOJI_PREFIX, '');
    if (Array.isArray(out.items)) out.items = out.items.map(clean);
    return out;
  }
  return item;
}

const sidebars = Object.fromEntries(
  Object.entries(source as Record<string, unknown>).map(([k, v]) => [k, clean(v)]),
) as SidebarsConfig;

export default sidebars;
