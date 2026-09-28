"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { cn } from "@/lib/utils";

/** Styled markdown for AI chat bubbles: headings, lists, tables, bold figures. */
export function Markdown({ children, className }: { children: string; className?: string }) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      className={cn("space-y-3 break-words", className)}
      components={{
        h1: (p) => <h3 className="text-base font-bold" {...p} />,
        h2: (p) => <h3 className="text-base font-bold" {...p} />,
        h3: (p) => <h4 className="text-sm font-bold" {...p} />,
        p: (p) => <p className="text-sm leading-relaxed" {...p} />,
        ul: (p) => <ul className="list-disc space-y-1 pl-5 text-sm" {...p} />,
        ol: (p) => <ol className="list-decimal space-y-1 pl-5 text-sm" {...p} />,
        li: (p) => <li className="leading-relaxed" {...p} />,
        strong: (p) => <strong className="font-medium" {...p} />,
        table: (p) => (
          <div className="overflow-x-auto rounded-lg border">
            <table className="w-full text-left text-sm" {...p} />
          </div>
        ),
        thead: (p) => <thead className="bg-muted/60" {...p} />,
        th: (p) => <th className="px-2.5 py-1.5 font-medium" {...p} />,
        td: (p) => <td className="border-t px-2.5 py-1.5 align-top" {...p} />,
        blockquote: (p) => (
          <blockquote className="border-l-2 border-leaf-500 pl-3 italic text-muted-foreground" {...p} />
        ),
        code: (p) => <code className="rounded bg-muted px-1 py-0.5 text-xs" {...p} />,
        a: (p) => <a className="text-leaf-600 underline" target="_blank" rel="noreferrer" {...p} />,
      }}
    >
      {children}
    </ReactMarkdown>
  );
}
