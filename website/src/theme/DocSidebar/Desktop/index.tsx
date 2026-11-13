import React, {type ReactNode} from 'react';
import {translate} from '@docusaurus/Translate';
import clsx from 'clsx';
import {useThemeConfig} from '@docusaurus/theme-common';
import Icon from '@site/src/components/docs/Icon';
import type {Props} from '@theme/DocSidebar/Desktop';
import SidebarMenu from '@site/src/components/docs/SidebarMenu';

/** Focus an element once the layout change has been painted (it may have been display:none). */
function focusSoon(selector: string, tries = 10) {
  requestAnimationFrame(() => {
    const el = document.querySelector<HTMLElement>(selector);
    if (el && el.getClientRects().length) el.focus();
    else if (tries > 0) focusSoon(selector, tries - 1);
  });
}

/** Desktop sidebar: the same two-level menu as the phone drawer. */
function DocSidebarDesktop({path, sidebar, onCollapse, isHidden}: Props): ReactNode {
  const {
    docs: {
      sidebar: {hideable},
    },
  } = useThemeConfig();
  return (
    <div className={clsx('it-dsb', isHidden && 'it-dsb--hidden')}>
      {hideable && (
        <div className="it-dsb__head">
          <button type="button" className="it-menubtn" onClick={() => {
              onCollapse();
              focusSoon('.it-menubtn--rail');
            }} aria-label={translate({id: 'menu.hide', message: 'Hide menu'})} title={translate({id: 'menu.hide', message: 'Hide menu'})}>
            <Icon name="menu" size={20} />
          </button>
          <span className="it-dsb__title">{translate({id: 'menu.title', message: 'Menu'})}</span>
        </div>
      )}
      <nav className="it-dsb__scroll" aria-label={translate({id: 'menu.sidebar', message: 'Docs sidebar'})}>
        <SidebarMenu sidebar={sidebar} path={path} />
      </nav>
    </div>
  );
}

export default React.memo(DocSidebarDesktop);
