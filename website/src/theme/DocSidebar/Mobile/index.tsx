import React, {useState, type ReactNode} from 'react';
import Link from '@docusaurus/Link';
import {NavbarSecondaryMenuFiller, type NavbarSecondaryMenuComponent} from '@docusaurus/theme-common';
import {useNavbarMobileSidebar} from '@docusaurus/theme-common/internal';
import type {PropSidebarItem, PropSidebarItemLink, PropSidebarItemCategory} from '@docusaurus/plugin-content-docs';
import type {Props} from '@theme/DocSidebar/Mobile';
import Icon from '@site/src/components/docs/Icon';

/**
 * The phone menu is a two-level drawer: the "Get started" pages as icon rows
 * and the other sections as rows that open their own page list, with a back
 * button. Level one never scrolls past the section names.
 */

const SECTION_ICON: Record<string, string> = {
  'nav-cat-start': 'rocket',
  'nav-cat-guides': 'book',
  'nav-cat-templates': 'layers',
  'nav-cat-examples': 'terminal',
  'nav-cat-reference': 'file',
  'nav-cat-security': 'shield',
  'nav-cat-contrib': 'code',
};

function pageIcon(item: PropSidebarItemLink): string {
  const h = item.href;
  if (/introduction/.test(h)) return 'info';
  if (/installation/.test(h)) return 'download';
  if (/quick-start/.test(h)) return 'terminal';
  if (/status/.test(h)) return 'check';
  return 'book';
}

function hasActive(item: PropSidebarItem, path: string): boolean {
  if (item.type === 'link') return item.href === path;
  if (item.type === 'category') return item.href === path || item.items.some((i) => hasActive(i, path));
  return false;
}

function Row({item, path, onGo, icon}: {item: PropSidebarItemLink; path: string; onGo: () => void; icon?: string}): ReactNode {
  const active = item.href === path;
  return (
    <li>
      <Link
        to={item.href}
        className={`it-mnav__row${active ? ' is-active' : ''}`}
        aria-current={active ? 'page' : undefined}
        onClick={onGo}>
        {icon && <Icon name={icon} size={18} />}
        <span>{item.label}</span>
      </Link>
    </li>
  );
}

function Pages({items, path, onGo}: {items: PropSidebarItem[]; path: string; onGo: () => void}): ReactNode {
  return (
    <>
      {items.map((item, i) => {
        if (item.type === 'link') return <Row key={item.href} item={item} path={path} onGo={onGo} />;
        if (item.type === 'category') {
          return (
            <React.Fragment key={`${item.label}-${i}`}>
              <li className="it-mnav__sub">{item.label}</li>
              {item.href && (
                <Row item={{type: 'link', href: item.href, label: item.label}} path={path} onGo={onGo} />
              )}
              <Pages items={item.items} path={path} onGo={onGo} />
            </React.Fragment>
          );
        }
        return null;
      })}
    </>
  );
}

const Menu: NavbarSecondaryMenuComponent<Props> = ({sidebar, path}) => {
  const mobile = useNavbarMobileSidebar();
  const close = () => mobile.toggle();
  const categories = sidebar.filter((i): i is PropSidebarItemCategory => i.type === 'category');
  const start = categories.find((c) => c.className?.includes('nav-cat-start'));
  const rest = categories.filter((c) => c !== start);
  const links = sidebar.filter((i): i is PropSidebarItemLink => i.type === 'link');
  const initial = rest.find((c) => hasActive(c, path))?.label ?? null;
  const [open, setOpen] = useState<string | null>(initial);
  const current = rest.find((c) => c.label === open);

  if (current) {
    return (
      <div className="it-mnav">
        <button type="button" className="it-mnav__back" onClick={() => setOpen(null)}>
          <Icon name="chevron-left" size={18} />
          <span>{current.label}</span>
        </button>
        <ul className="it-mnav__list">
          {current.href && (
            <Row item={{type: 'link', href: current.href, label: `${current.label} overview`}} path={path} onGo={close} />
          )}
          <Pages items={current.items} path={path} onGo={close} />
        </ul>
      </div>
    );
  }

  return (
    <div className="it-mnav">
      <p className="it-mnav__label">{start?.label ?? 'Get started'}</p>
      <ul className="it-mnav__list">
        {links.map((l) => (
          <Row key={l.href} item={{...l, label: 'Overview'}} path={path} onGo={close} icon="book" />
        ))}
        {start?.items
          .filter((i): i is PropSidebarItemLink => i.type === 'link')
          .map((l) => (
            <Row key={l.href} item={l} path={path} onGo={close} icon={pageIcon(l)} />
          ))}
      </ul>
      <p className="it-mnav__label">Documentation</p>
      <ul className="it-mnav__list">
        {rest.map((c) => (
          <li key={c.label}>
            <button
              type="button"
              className={`it-mnav__row it-mnav__row--section${hasActive(c, path) ? ' is-current' : ''}`}
              onClick={() => setOpen(c.label)}>
              <Icon name={SECTION_ICON[(c.className ?? '').split(' ').find((n) => n in SECTION_ICON) ?? ''] ?? 'file'} size={18} />
              <span>{c.label}</span>
              <Icon name="chevron-right" size={16} />
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
};

function DocSidebarMobile(props: Props): ReactNode {
  return <NavbarSecondaryMenuFiller component={Menu} props={props} />;
}

export default React.memo(DocSidebarMobile);
