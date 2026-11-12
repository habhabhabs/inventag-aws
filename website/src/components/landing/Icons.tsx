/**
 * Line icons for the landing page, drawn for this site on a 24px grid with a
 * 1.5px stroke, square-ish joins and no fills, to match the logo's
 * geometry. Decorative: always aria-hidden, the text next to them carries
 * the meaning.
 */
import React, {type ReactNode, type SVGProps} from 'react';

function Svg({children, ...props}: SVGProps<SVGSVGElement> & {children: ReactNode}): ReactNode {
  return (
    <svg
      width="24"
      height="24"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="square"
      strokeLinejoin="miter"
      aria-hidden="true"
      focusable="false"
      {...props}>
      {children}
    </svg>
  );
}

export const IconScan = () => (
  <Svg>
    <path d="M4 8V4h4M16 4h4v4M20 16v4h-4M8 20H4v-4" />
    <path d="M8 9h8M8 12h5M8 15h3" />
  </Svg>
);

export const IconSheet = () => (
  <Svg>
    <rect x="4" y="3.75" width="16" height="16.5" />
    <path d="M4 9h16M4 14.5h16M10 9v11.25" />
  </Svg>
);

export const IconAccounts = () => (
  <Svg>
    <rect x="3.75" y="8" width="11" height="11.25" />
    <path d="M7 8V4.75h11.25V16H14.75" />
    <path d="M7 12.5h4.5M7 15.5h2.5" />
  </Svg>
);

export const IconTag = () => (
  <Svg>
    <path d="M3.75 6.75h10.5l6 5.25-6 5.25H3.75z" />
    <circle cx="15" cy="12" r="1" />
    <path d="M6.75 10.5h4M6.75 13.5h2.5" />
  </Svg>
);

export const IconHistory = () => (
  <Svg>
    <path d="M4.5 12a7.5 7.5 0 1 0 2.2-5.3" />
    <path d="M4.5 4.5v3.75h3.75" />
    <path d="M12 8v4.25l3 1.75" />
  </Svg>
);

export const IconNetwork = () => (
  <Svg>
    <rect x="9.25" y="3.75" width="5.5" height="5.5" />
    <rect x="3.75" y="14.75" width="5.5" height="5.5" />
    <rect x="14.75" y="14.75" width="5.5" height="5.5" />
    <path d="M12 9.25v2.75M6.5 14.75V12h11v2.75" />
  </Svg>
);

export const IconTemplate = () => (
  <Svg>
    <rect x="3.75" y="3.75" width="16.5" height="16.5" />
    <path d="M3.75 9h16.5M9 9v11.25" />
    <path d="M12 12.75h5.25M12 15.75h3" />
  </Svg>
);

export const IconCheck = () => (
  <Svg>
    <path d="M12 3.5 19.5 6v5.5c0 4.25-3.1 7.6-7.5 9-4.4-1.4-7.5-4.75-7.5-9V6z" />
    <path d="m8.75 12 2.25 2.25 4.25-4.5" />
  </Svg>
);

export const IconArrow = () => (
  <Svg width="18" height="18">
    <path d="M5 12h13M13 7l5 5-5 5" />
  </Svg>
);

export const IconCopy = () => (
  <Svg width="16" height="16">
    <rect x="8.75" y="8.75" width="11.5" height="11.5" />
    <path d="M15.25 8.75v-5H3.75v11.5h5" />
  </Svg>
);

export const IconDone = () => (
  <Svg width="16" height="16">
    <path d="m4.5 12.5 4.5 4.5 10.5-10.5" />
  </Svg>
);
