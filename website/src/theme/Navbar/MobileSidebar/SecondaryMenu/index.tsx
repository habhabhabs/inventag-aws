import React, {type ReactNode} from 'react';
import {useThemeConfig} from '@docusaurus/theme-common';
import {useNavbarSecondaryMenu} from '@docusaurus/theme-common/internal';
import Translate from '@docusaurus/Translate';

/**
 * Same as the theme's own component, with one change: "Back to main menu"
 * unmounts the button that has focus, which drops focus to the page body.
 * After going back, focus moves to the first item of the main menu.
 * The main menu panel is inert until React has re-rendered and may still be
 * fading in, so focus is tried on each frame (at most about half a second).
 */
function focusFirstMainItem(tries = 30) {
  const first = document.querySelector<HTMLElement>(
    '.navbar-sidebar__items > .navbar-sidebar__item:first-child .menu__link',
  );
  if (first) first.focus();
  if (document.activeElement !== first && tries > 0) {
    requestAnimationFrame(() => focusFirstMainItem(tries - 1));
  }
}

function SecondaryMenuBackButton(props: React.ComponentProps<'button'>) {
  return (
    <button {...props} type="button" className="clean-btn navbar-sidebar__back">
      <Translate
        id="theme.navbar.mobileSidebarSecondaryMenu.backButtonLabel"
        description="The label of the back button to return to main menu, inside the mobile navbar sidebar secondary menu (notably used to display the docs sidebar)">
        ← Back to main menu
      </Translate>
    </button>
  );
}

// The secondary menu slides from the right and shows contextual information
// such as the docs sidebar
export default function NavbarMobileSidebarSecondaryMenu(): ReactNode {
  const isPrimaryMenuEmpty = useThemeConfig().navbar.items.length === 0;
  const secondaryMenu = useNavbarSecondaryMenu();
  return (
    <>
      {/* edge-case: prevent returning to the primaryMenu when it's empty */}
      {!isPrimaryMenuEmpty && (
        <SecondaryMenuBackButton
          onClick={() => {
            secondaryMenu.hide();
            requestAnimationFrame(() => focusFirstMainItem());
          }}
        />
      )}
      {secondaryMenu.content}
    </>
  );
}
