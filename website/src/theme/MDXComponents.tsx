import MDXComponents from '@theme-original/MDXComponents';
import Table from './MDXComponents/Table';
import {Card, CardGroup} from '@site/src/components/docs/Card';
import Icon from '@site/src/components/docs/Icon';

// Default MDX components, a scroll wrapper for tables, and the doc tiles
// (Card, CardGroup, Icon) so .mdx pages can use them without imports.
export default {
  ...MDXComponents,
  table: Table,
  Card,
  CardGroup,
  Icon,
};
