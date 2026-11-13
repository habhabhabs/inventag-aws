import React, {type ReactNode} from 'react';
import Link from '@docusaurus/Link';
import Icon from './Icon';

type CardProps = {
  title: string;
  /** A name from the icon set (see Icon.tsx). */
  icon?: string;
  /** Doc route, for example /docs/getting-started/quick-start, or an https:// URL. */
  href?: string;
  children?: ReactNode;
};

/** A tile that links to another page: icon, title, one-line description. */
export function Card({title, icon, href, children}: CardProps): ReactNode {
  const body = (
    <>
      {icon && (
        <span className="it-card__icon">
          <Icon name={icon} size={20} />
        </span>
      )}
      <span className="it-card__title">{title}</span>
      {children && <span className="it-card__body">{children}</span>}
      {href && (
        <span className="it-card__go" aria-hidden="true">
          <Icon name="arrow" size={16} />
        </span>
      )}
    </>
  );
  return href ? (
    <Link className="it-card it-card--link" to={href}>
      {body}
    </Link>
  ) : (
    <div className="it-card">{body}</div>
  );
}

/** A responsive grid of cards: cols is 2 (default), 3 or 4 on wide screens. */
export function CardGroup({cols = 2, children}: {cols?: 2 | 3 | 4; children: ReactNode}): ReactNode {
  return <div className={`it-cards it-cards--${cols}`}>{children}</div>;
}
