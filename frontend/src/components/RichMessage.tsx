import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeHighlight from 'rehype-highlight';
import 'highlight.js/styles/github.css';

interface RichMessageProps {
  content: string;
  role: 'user' | 'assistant';
}

const RichMessage: React.FC<RichMessageProps> = ({ content, role }) => {
  const isUser = role === 'user';

  if (isUser) {
    // Simple text for user messages
    return <div className="whitespace-pre-wrap">{content}</div>;
  }

  // Rich markdown rendering for assistant messages using Tailwind Typography
  return (
    <div className="prose prose-lg max-w-none prose-gray">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeHighlight]}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
};

export default RichMessage;
