import React, {type ReactNode} from 'react';
import clsx from 'clsx';
import {useThemeConfig} from '@docusaurus/theme-common';
import Icon from '@site/src/components/docs/Icon';
import type {Props} from '@theme/DocSidebar/Desktop';
import SidebarMenu from '@site/src/components/docs/SidebarMenu';

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
          <button type="button" className="it-menubtn" onClick={onCollapse} aria-label="Hide menu" title="Hide menu">
            <Icon name="menu" size={20} />
          </button>
          <span className="it-dsb__title">Menu</span>
        </div>
      )}
      <nav className="it-dsb__scroll" aria-label="Docs sidebar">
        <SidebarMenu sidebar={sidebar} path={path} />
      </nav>
    </div>
  );
}

export default React.memo(DocSidebarDesktop);
