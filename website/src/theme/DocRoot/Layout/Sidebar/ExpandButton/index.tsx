import React, {type ReactNode} from 'react';
import Icon from '@site/src/components/docs/Icon';

/** Collapsed sidebar: a menu button (not an arrow) brings the menu back. */
export default function ExpandButton({toggleSidebar}: {toggleSidebar: () => void}): ReactNode {
  return (
    <button type="button" className="it-menubtn it-menubtn--rail" onClick={toggleSidebar} aria-label="Show menu" title="Show menu">
      <Icon name="menu" size={20} />
    </button>
  );
}
