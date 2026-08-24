// ChatMarkdown — tiny renderer for the assistant's constrained response
// format: **bold** (standalone line = section heading), "- " bullet lists,
// numbered lists and pipe tables ("| a | b |" with a |---| separator row).
// Deliberately dependency-free so both customer and admin chat bubbles
// render identical structure without pulling in a markdown library.
import type { ReactNode } from "react"

function renderInline(text: string, keyPrefix: string): ReactNode[] {
  return text.split(/(\*\*[^*]+\*\*)/g).map((part, i) => {
    if (part.startsWith("**") && part.endsWith("**") && part.length > 4) {
      return (
        <strong key={`${keyPrefix}-${i}`} className="font-semibold">
          {part.slice(2, -2)}
        </strong>
      )
    }
    return <span key={`${keyPrefix}-${i}`}>{part}</span>
  })
}

type Row = string[]

function parseTable(lines: string[], start: number): { rows: Row[]; end: number } {
  const rows: Row[] = []
  let i = start
  while (i < lines.length && lines[i].trim().startsWith("|")) {
    const cells = lines[i]
      .trim()
      .replace(/^\|/, "")
      .replace(/\|$/, "")
      .split("|")
      .map((c) => c.trim())
    // Skip the |---|---| alignment row.
    if (!cells.every((c) => /^:?-{3,}:?$/.test(c))) {
      rows.push(cells)
    }
    i += 1
  }
  return { rows, end: i - 1 }
}

export function ChatMarkdown({ content }: { content: string }) {
  const lines = content.split("\n")
  const nodes: ReactNode[] = []
  let listBuffer: { ordered: boolean; text: string }[] = []

  const flushList = (key: string) => {
    if (!listBuffer.length) return
    const ordered = listBuffer[0].ordered
    const items = listBuffer.map((it, idx) => (
      <li key={`${key}-li-${idx}`} className="leading-snug">
        {renderInline(it.text, `${key}-li-${idx}`)}
      </li>
    ))
    nodes.push(
      ordered ? (
        <ol key={key} className="ml-4 list-decimal space-y-0.5">
          {items}
        </ol>
      ) : (
        <ul key={key} className="ml-4 list-disc space-y-0.5">
          {items}
        </ul>
      )
    )
    listBuffer = []
  }

  for (let i = 0; i < lines.length; i += 1) {
    const raw = lines[i]
    const line = raw.trim()
    const key = `b-${i}`

    // Table block.
    if (line.startsWith("|")) {
      flushList(`${key}-prelist`)
      const { rows, end } = parseTable(lines, i)
      if (rows.length) {
        const [head, ...body] = rows
        nodes.push(
          <table key={key} className="w-full border-collapse text-xs">
            <thead>
              <tr>
                {head.map((cell, ci) => (
                  <th
                    key={`h-${ci}`}
                    className="border-b border-border px-1.5 py-1 text-left font-semibold whitespace-nowrap"
                  >
                    {cell}
                  </th>
                ))}
              </tr>
            </thead>
            {body.length > 0 && (
              <tbody>
                {body.map((row, ri) => (
                  <tr key={`r-${ri}`}>
                    {row.map((cell, ci) => (
                      <td
                        key={`c-${ri}-${ci}`}
                        className="border-b border-border/40 px-1.5 py-1 align-top"
                      >
                        {renderInline(cell, `c-${ri}-${ci}`)}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            )}
          </table>
        )
      }
      i = end
      continue
    }

    // Bullet list item.
    if (/^[-•]\s+/.test(line)) {
      listBuffer.push({ ordered: false, text: line.replace(/^[-•]\s+/, "") })
      continue
    }

    // Numbered list item.
    const numbered = line.match(/^(\d+)[.)]\s+(.*)$/)
    if (numbered) {
      listBuffer.push({ ordered: true, text: numbered[2] })
      continue
    }

    flushList(`${key}-flush`)

    if (!line) continue

    // Standalone **bold** line = section heading.
    if (/^\*\*[^*]+\*\*$/.test(line)) {
      nodes.push(
        <p key={key} className="mt-1.5 text-sm font-semibold first:mt-0">
          {line.slice(2, -2)}
        </p>
      )
      continue
    }

    nodes.push(
      <p key={key} className="text-sm leading-snug break-words">
        {renderInline(line, key)}
      </p>
    )
  }

  flushList("tail")

  return <div className="space-y-1">{nodes}</div>
}
