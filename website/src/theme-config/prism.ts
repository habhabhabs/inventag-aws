import type {PrismTheme} from 'prism-react-renderer';

/**
 * Syntax colours for code blocks, matched to the site palette.
 * Every token colour is at least 4.5:1 against its code background
 * (light #F3F1EC, dark #161615), and against the highlighted-line
 * background. The ratios are listed in website/brand/README.md.
 */
export const inventagLight: PrismTheme = {
  plain: {color: '#141413', backgroundColor: '#F3F1EC'},
  styles: [
    {types: ['comment', 'prolog', 'doctype', 'cdata'], style: {color: '#66645E', fontStyle: 'normal'}},
    {types: ['punctuation', 'operator'], style: {color: '#575652'}},
    {types: ['keyword', 'selector', 'important', 'atrule', 'rule'], style: {color: '#B83A21'}},
    {types: ['string', 'char', 'attr-value', 'inserted', 'regex', 'url'], style: {color: '#2F6B3A'}},
    {types: ['function', 'class-name', 'builtin'], style: {color: '#1F4E8C'}},
    {types: ['number', 'boolean', 'constant', 'symbol', 'unit'], style: {color: '#8A4B00'}},
    {types: ['property', 'attr-name', 'tag', 'key'], style: {color: '#6B3F8C'}},
    {types: ['variable', 'parameter'], style: {color: '#2F5D7C'}},
    {types: ['deleted'], style: {color: '#B83A21'}},
    {types: ['bold', 'important'], style: {fontWeight: '600'}},
    {types: ['italic'], style: {fontStyle: 'italic'}},
  ],
};

export const inventagDark: PrismTheme = {
  plain: {color: '#F2F0EC', backgroundColor: '#161615'},
  styles: [
    {types: ['comment', 'prolog', 'doctype', 'cdata'], style: {color: '#9C998F', fontStyle: 'normal'}},
    {types: ['punctuation', 'operator'], style: {color: '#B5B2AA'}},
    {types: ['keyword', 'selector', 'important', 'atrule', 'rule'], style: {color: '#F07A5F'}},
    {types: ['string', 'char', 'attr-value', 'inserted', 'regex', 'url'], style: {color: '#A9C98F'}},
    {types: ['function', 'class-name', 'builtin'], style: {color: '#8DB4E2'}},
    {types: ['number', 'boolean', 'constant', 'symbol', 'unit'], style: {color: '#E0B070'}},
    {types: ['property', 'attr-name', 'tag', 'key'], style: {color: '#C9A6E0'}},
    {types: ['variable', 'parameter'], style: {color: '#8FC1D9'}},
    {types: ['deleted'], style: {color: '#F07A5F'}},
    {types: ['bold', 'important'], style: {fontWeight: '600'}},
    {types: ['italic'], style: {fontStyle: 'italic'}},
  ],
};
