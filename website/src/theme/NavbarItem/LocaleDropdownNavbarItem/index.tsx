import React, {type ReactNode} from 'react';
import LocaleDropdownNavbarItem from '@theme-original/NavbarItem/LocaleDropdownNavbarItem';
import type {Props} from '@theme/NavbarItem/LocaleDropdownNavbarItem';
import {AddressLocaleScope} from '@site/src/address/addressLocale';

/**
 * On the 404 page under /fr/ (and the other languages) the theme would mark
 * English as the current language and build the other links from the wrong
 * address (/es/fr/...). Drawn inside AddressLocaleScope, the theme's own
 * dropdown shows the language of the address as current and links to the same
 * address in the other languages. Elsewhere the scope changes nothing.
 */
export default function LocaleDropdownNavbarItemWrapper(props: Props): ReactNode {
  return (
    <AddressLocaleScope>
      <LocaleDropdownNavbarItem {...props} />
    </AddressLocaleScope>
  );
}
