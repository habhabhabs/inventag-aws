import React, {type ReactNode} from 'react';
import {NavbarSecondaryMenuFiller, type NavbarSecondaryMenuComponent} from '@docusaurus/theme-common';
import {useNavbarMobileSidebar} from '@docusaurus/theme-common/internal';
import type {Props} from '@theme/DocSidebar/Mobile';
import SidebarMenu from '@site/src/components/docs/SidebarMenu';

/** The phone menu: the shared two-level menu, closing the drawer on navigation. */
const Menu: NavbarSecondaryMenuComponent<Props> = ({sidebar, path}) => {
  const mobile = useNavbarMobileSidebar();
  return <SidebarMenu sidebar={sidebar} path={path} onGo={() => mobile.toggle()} />;
};

function DocSidebarMobile(props: Props): ReactNode {
  return <NavbarSecondaryMenuFiller component={Menu} props={props} />;
}

export default React.memo(DocSidebarMobile);
