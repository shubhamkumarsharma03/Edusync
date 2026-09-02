import React from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

interface MarkdownContentProps {
  content: string
  className?: string
}

export const MarkdownContent: React.FC<MarkdownContentProps> = ({ content, className = '' }) => {
  // Clean up any internal raw markers or repeated separators
  const cleanedContent = content
    .replace(/^---\s*Document Notice\s*---\s*$/gim, '')
    .replace(/\n{3,}/g, '\n\n')
    .trim()

  return (
    <div className={`markdown-content leading-relaxed text-[#18181b] space-y-2.5 text-sm sm:text-[15px] ${className}`}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          h1: ({ children }) => (
            <h1 className="text-base sm:text-lg font-bold text-neutral-900 mt-3 mb-1.5 pb-1 border-b border-neutral-200 flex items-center gap-1.5">
              {children}
            </h1>
          ),
          h2: ({ children }) => (
            <h2 className="text-sm sm:text-base font-bold text-neutral-900 mt-2.5 mb-1 text-indigo-950">
              {children}
            </h2>
          ),
          h3: ({ children }) => (
            <h3 className="text-sm font-semibold text-neutral-900 mt-2 mb-1">
              {children}
            </h3>
          ),
          p: ({ children }) => (
            <p className="mb-2 leading-relaxed last:mb-0">
              {children}
            </p>
          ),
          strong: ({ children }) => (
            <strong className="font-semibold text-neutral-950">{children}</strong>
          ),
          em: ({ children }) => (
            <em className="italic text-neutral-800">{children}</em>
          ),
          ul: ({ children }) => (
            <ul className="list-disc list-outside pl-4 space-y-1 my-2 text-neutral-800">
              {children}
            </ul>
          ),
          ol: ({ children }) => (
            <ol className="list-decimal list-outside pl-4 space-y-1 my-2 text-neutral-800">
              {children}
            </ol>
          ),
          li: ({ children }) => (
            <li className="leading-relaxed pl-0.5">{children}</li>
          ),
          a: ({ href, children }) => (
            <a
              href={href}
              target="_blank"
              rel="noopener noreferrer"
              className="text-indigo-600 hover:text-indigo-800 underline underline-offset-2 break-all font-medium transition-colors"
            >
              {children}
            </a>
          ),
          blockquote: ({ children }) => (
            <blockquote className="border-l-4 border-indigo-400 pl-3 py-1 my-2 text-neutral-700 bg-indigo-50/60 rounded-r text-xs sm:text-sm">
              {children}
            </blockquote>
          ),
          code: ({ className, children }) => {
            const isInline = !className && typeof children === 'string' && !children.includes('\n')
            return isInline ? (
              <code className="bg-neutral-200/80 text-neutral-850 px-1.5 py-0.5 rounded text-xs font-mono font-medium">
                {children}
              </code>
            ) : (
              <pre className="bg-neutral-900 text-neutral-100 p-3 rounded-lg overflow-x-auto text-xs font-mono my-2">
                <code>{children}</code>
              </pre>
            )
          },
          hr: () => <hr className="my-3 border-neutral-200" />,
          table: ({ children }) => (
            <div className="overflow-x-auto my-2 rounded-lg border border-neutral-200">
              <table className="min-w-full divide-y divide-neutral-200 text-xs sm:text-sm">
                {children}
              </table>
            </div>
          ),
          thead: ({ children }) => (
            <thead className="bg-neutral-100 text-neutral-700 font-semibold">{children}</thead>
          ),
          tbody: ({ children }) => (
            <tbody className="divide-y divide-neutral-200 bg-white">{children}</tbody>
          ),
          tr: ({ children }) => <tr className="hover:bg-neutral-50/50">{children}</tr>,
          th: ({ children }) => (
            <th className="px-3 py-2 text-left font-semibold text-neutral-800">{children}</th>
          ),
          td: ({ children }) => (
            <td className="px-3 py-2 text-neutral-700 align-top">{children}</td>
          ),
        }}
      >
        {cleanedContent}
      </ReactMarkdown>
    </div>
  )
}
