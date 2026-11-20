import {useEffect, type RefObject} from 'react';
import {translate} from '@docusaurus/Translate';

/**
 * Code blocks (`pre`) inside `container`: when, and only when, a block is wider
 * than its box, it becomes a focusable, named group (WCAG 2.1.1, 4.1.2) and
 * gets `data-scroll-start` / `data-scroll-end` on each side that still has code
 * to reveal (custom.css fades that edge). A block that fits is not a Tab stop.
 * The same rule as the tables (src/theme/MDXComponents/Table.tsx).
 * Without JavaScript the blocks render as built: whole, scrollable, no fade.
 */
export default function useCodeOverflow(container: RefObject<HTMLElement | null>, selector = 'pre'): void {
  useEffect(() => {
    const root = container.current;
    if (!root) return undefined;
    const label = translate({id: 'code.scrollHint', message: 'Code. Scroll sideways to see all of it.'});
    const blocks = Array.from(root.querySelectorAll<HTMLElement>(selector));
    const frames = new Map<HTMLElement, number>();
    const sync = (pre: HTMLElement) => {
      // one read pass, then writes
      const {scrollWidth, clientWidth, scrollLeft} = pre;
      const over = scrollWidth > clientWidth + 1;
      if (over) {
        pre.tabIndex = 0;
        pre.setAttribute('role', 'group'); // not a landmark: a page has many, as with tables
        pre.setAttribute('aria-label', label);
      } else {
        pre.removeAttribute('tabindex');
        pre.removeAttribute('role');
        pre.removeAttribute('aria-label');
      }
      pre.toggleAttribute('data-scroll-start', over && scrollLeft > 1);
      pre.toggleAttribute('data-scroll-end', over && scrollLeft + clientWidth < scrollWidth - 1);
    };
    const later = (pre: HTMLElement) => {
      cancelAnimationFrame(frames.get(pre) ?? 0);
      frames.set(pre, requestAnimationFrame(() => sync(pre)));
    };
    const onScroll = (e: Event) => later(e.currentTarget as HTMLElement);
    const ro = new ResizeObserver((entries) => entries.forEach((en) => later(en.target as HTMLElement)));
    blocks.forEach((pre) => {
      sync(pre);
      ro.observe(pre);
      pre.addEventListener('scroll', onScroll, {passive: true});
    });
    document.fonts?.ready.then(() => blocks.forEach(later));
    return () => {
      ro.disconnect();
      blocks.forEach((pre) => pre.removeEventListener('scroll', onScroll));
      frames.forEach((f) => cancelAnimationFrame(f));
    };
  }, [container, selector]);
}
