import React, {type ReactNode} from 'react';
import Heading from '@theme-original/Heading';
import type HeadingType from '@theme/Heading';
import type {WrapperProps} from '@docusaurus/types';

type Props = WrapperProps<typeof HeadingType>;

const STEP = /^(\d{1,2})\.\s+/;

/**
 * "## 1. Do the thing" headings render as numbered steps: the number moves
 * into a badge, the heading keeps its anchor.
 */
export default function HeadingWrapper(props: Props): ReactNode {
  const {as, children} = props;
  if ((as === 'h2' || as === 'h3') && children) {
    const list = React.Children.toArray(children);
    const first = list[0];
    if (typeof first === 'string') {
      const m = STEP.exec(first);
      if (m) {
        return (
          <Heading
            {...props}
            className={[props.className, 'it-step'].filter(Boolean).join(' ')}
            data-step={m[1]}>
            {[first.slice(m[0].length), ...list.slice(1)]}
          </Heading>
        );
      }
    }
  }
  return <Heading {...props} />;
}
