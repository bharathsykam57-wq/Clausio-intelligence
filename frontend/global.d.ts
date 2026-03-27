declare module 'isomorphic-dompurify' {
  const DOMPurify: {
    sanitize(source: string): string;
  };
  export default DOMPurify;
}

declare module 'marked' {
  export const marked: {
    parse(src: string): string;
  };
}
