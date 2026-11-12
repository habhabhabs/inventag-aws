import React, {useEffect, useRef, useState, type ComponentProps, type ReactNode} from 'react';

/**
 * Markdown tables scroll sideways inside a framed wrapper instead of
 * widening the page. When (and only when) a table overflows, the wrapper
 * becomes focusable so keyboard users can scroll it (WCAG 2.1.1).
 */
export default function Table(props: ComponentProps<'table'>): ReactNode {
  const ref = useRef<HTMLDivElement>(null);
  const [scrollable, setScrollable] = useState(false);
  useEffect(() => {
    const el = ref.current;
    if (!el) return undefined;
    const update = () => setScrollable(el.scrollWidth > el.clientWidth + 1);
    update();
    const ro = new ResizeObserver(update);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  return (
    <div
      ref={ref}
      className="table-scroll"
      tabIndex={scrollable ? 0 : undefined}>
      <table {...props} />
    </div>
  );
}
