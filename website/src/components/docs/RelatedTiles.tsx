import React, {type ReactNode} from 'react';
import {translate} from '@docusaurus/Translate';
import Link from '@docusaurus/Link';
import {useDocById, useAllDocsData} from '@docusaurus/plugin-content-docs/client';
import Icon from './Icon';
import {RELATED} from '@site/src/data/related';

function Tile({id, icon, to}: {id: string; icon: string; to?: string}): ReactNode {
  const doc = useDocById(id);
  if (!doc || !to) return null;
  return (
    <Link className="it-card it-card--link" to={to}>
      <span className="it-card__icon">
        <Icon name={icon} size={20} />
      </span>
      <span className="it-card__title">{doc.title}</span>
      {doc.description && <span className="it-card__body">{doc.description}</span>}
      <span className="it-card__go" aria-hidden="true">
        <Icon name="arrow" size={16} />
      </span>
    </Link>
  );
}

/** Curated next-step tiles for the page being read (see src/data/related.ts). */
export default function RelatedTiles({docId}: {docId: string}): ReactNode {
  const entry = RELATED[docId];
  if (!entry) return null;
  const paths = new Map<string, string>(
    Object.values(useAllDocsData()).flatMap((p) => p.versions.filter((v) => v.isLast).flatMap((v) => v.docs.map((d) => [d.id, d.path] as [string, string]))),
  );
  const defaults = ['arrow', 'book', 'layers', 'file'];
  return (
    <aside className="it-related" aria-labelledby="it-related-title">
      <h2 id="it-related-title" className="it-related__title">
        {translate({id: 'related.title', message: 'Where to next'})}
      </h2>
      <div className={`it-cards it-cards--${entry.ids.length >= 4 ? 2 : entry.ids.length === 3 ? 3 : 2}`}>
        {entry.ids.map((id, i) => (
          <Tile key={id} to={paths.get(id)} id={id} icon={entry.icons?.[i] ?? defaults[i % defaults.length]} />
        ))}
      </div>
    </aside>
  );
}
