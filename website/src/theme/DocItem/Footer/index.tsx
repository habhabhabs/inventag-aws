import React, {type ReactNode} from 'react';
import Footer from '@theme-original/DocItem/Footer';
import type FooterType from '@theme/DocItem/Footer';
import type {WrapperProps} from '@docusaurus/types';
import {useDoc, useDocsVersion} from '@docusaurus/plugin-content-docs/client';
import RelatedTiles from '@site/src/components/docs/RelatedTiles';

type Props = WrapperProps<typeof FooterType>;

export default function FooterWrapper(props: Props): ReactNode {
  const {metadata} = useDoc();
  const version = useDocsVersion();
  return (
    <>
      {version.isLast && <RelatedTiles docId={metadata.id} />}
      <Footer {...props} />
    </>
  );
}
