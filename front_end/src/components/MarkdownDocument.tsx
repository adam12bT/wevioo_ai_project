import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

interface MarkdownDocumentProps {
  content: string;
  className?: string;
}

export function MarkdownDocument({ content, className = '' }: MarkdownDocumentProps) {
  if (!content) {
    return <p className="text-sm text-slate-400 italic">No content available.</p>;
  }
  return (
    <div className={`markdown-body ${className}`}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          a: ({ href, children }) => (
            <a href={href} target="_blank" rel="noopener noreferrer">
              {children}
            </a>
          ),
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
