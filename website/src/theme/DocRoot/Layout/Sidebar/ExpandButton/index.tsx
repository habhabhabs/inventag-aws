import React, {type ReactNode} from 'react';
import {translate} from '@docusaurus/Translate';
import Icon from '@site/src/components/docs/Icon';

/** Collapsed sidebar: a menu button (not an arrow) brings the menu back. */
export default function ExpandButton({toggleSidebar}: {toggleSidebar: () => void}): ReactNode {
  return (
    <button type="button" className="it-menubtn it-menubtn--rail" onClick={() => {
        toggleSidebar();
        const focusHide = (tries = 10) =>
          requestAnimationFrame(() => {
            const el = document.querySelector<HTMLElement>('.it-dsb__head .it-menubtn');
            if (el && el.getClientRects().length) el.focus();
            else if (tries > 0) focusHide(tries - 1);
          });
        focusHide();
      }} aria-label={translate({id: 'menu.show', message: 'Show menu'})} title={translate({id: 'menu.show', message: 'Show menu'})}>
      <Icon name="menu" size={18} />
      <span>{translate({id: 'menu.title', message: 'Menu'})}</span>
    </button>
  );
}
