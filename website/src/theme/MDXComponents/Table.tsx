import React, {useEffect, useRef, useState, type ComponentProps, type ReactNode} from 'react';
import {translate} from '@docusaurus/Translate';

/**
 * Markdown tables scroll sideways inside a framed wrapper instead of
 * widening the page. When (and only when) a table overflows, the scroller
 * becomes a focusable, named region (WCAG 2.1.1, 4.1.2) and the frame shows an
 * edge tab on each side that still has columns to reveal. The first column
 * stays in view while scrolling (see custom.css).
 */
export default function Table(props: ComponentProps<'table'>): ReactNode {
  const ref = useRef<HTMLDivElement>(null);
  const [scrollable, setScrollable] = useState(false);
  const [atStart, setAtStart] = useState(true);
  const [atEnd, setAtEnd] = useState(false);
  const [wide, setWide] = useState(false); // three or more columns
  useEffect(() => {
    const el = ref.current;
    if (!el) return undefined;
    let frame = 0;
    const update = () => {
      setScrollable(el.scrollWidth > el.clientWidth + 1);
      setAtStart(el.scrollLeft <= 1);
      setAtEnd(el.scrollLeft + el.clientWidth >= el.scrollWidth - 1);
      setWide((el.querySelector('tr')?.children.length ?? 0) >= 3);
    };
    const onScroll = () => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(update);
    };
    update();
    const ro = new ResizeObserver(update);
    ro.observe(el);
    el.addEventListener('scroll', onScroll, {passive: true});
    return () => {
      ro.disconnect();
      el.removeEventListener('scroll', onScroll);
      cancelAnimationFrame(frame);
    };
  }, []);
  return (
    <div className="table-frame" data-scrollable={scrollable ? '' : undefined} data-wide={wide ? '' : undefined}>
      <div
        ref={ref}
        className="table-scroll"
        tabIndex={scrollable ? 0 : undefined}
        role={scrollable ? 'region' : undefined}
        aria-label={scrollable ? translate({id: 'table.scrollHint', message: 'Table. Scroll sideways to see all columns.'}) : undefined}>
        <table {...props} />
      </div>
      {scrollable && !atStart && (
        <span className="table-frame__edge table-frame__edge--start" aria-hidden="true">
          ‹
        </span>
      )}
      {scrollable && !atEnd && (
        <span className="table-frame__edge table-frame__edge--end" aria-hidden="true">
          ›
        </span>
      )}
    </div>
  );
}
