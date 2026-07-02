import type { OutputBlock, OutputTone } from "@/lib/run-output";

export function AnswerCard({ block }: { block: OutputBlock }) {
  const Icon = block.icon;

  return (
    <article className={answerCardClass(block.tone)}>
      <div className="flex gap-3">
        <div className={answerIconClass(block.tone)}>
          <Icon className="h-4 w-4" aria-hidden="true" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className={answerLabelClass(block.tone)}>{block.label}</span>
            <h3 className="text-sm font-semibold text-foreground">{block.title}</h3>
          </div>
          <StructuredText text={block.body} />
        </div>
      </div>
    </article>
  );
}

function StructuredText({ text }: { text: string }) {
  const lines = text.split("\n");

  return (
    <div className="mt-3 space-y-1.5">
      {lines.map((line, index) => (
        <StructuredLine key={`${line}-${index}`} line={line} />
      ))}
    </div>
  );
}

function StructuredLine({ line }: { line: string }) {
  const indent = Math.min(3, Math.floor((line.match(/^\s*/)?.[0].length ?? 0) / 2));
  const trimmed = line.trim();

  if (!trimmed) {
    return <div className="h-1" />;
  }

  const bullet = trimmed.match(/^[-*]\s+(.*)$/);
  if (bullet) {
    return (
      <div className="flex gap-2 text-sm leading-6 text-foreground" style={{ paddingLeft: `${indent * 14}px` }}>
        <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-primary/80" />
        <span className="min-w-0 break-words">
          <InlineCodeText text={bullet[1]} />
        </span>
      </div>
    );
  }

  const numbered = trimmed.match(/^(\d+)\.\s+(.*)$/);
  if (numbered) {
    return (
      <div className="flex gap-2 text-sm leading-6 text-foreground" style={{ paddingLeft: `${indent * 14}px` }}>
        <span className="mt-0.5 flex h-5 min-w-5 shrink-0 items-center justify-center rounded-sm border border-border bg-muted px-1 text-[10px] text-muted-foreground">
          {numbered[1]}
        </span>
        <span className="min-w-0 break-words">
          <InlineCodeText text={numbered[2]} />
        </span>
      </div>
    );
  }

  return (
    <p className="break-words text-sm leading-6 text-foreground" style={{ paddingLeft: `${indent * 14}px` }}>
      <InlineCodeText text={trimmed} />
    </p>
  );
}

function InlineCodeText({ text }: { text: string }) {
  return text.split(/(`[^`]+`)/g).map((part, index) => {
    if (part.startsWith("`") && part.endsWith("`")) {
      return (
        <code
          key={`${part}-${index}`}
          className="rounded-sm border border-border bg-background px-1.5 py-0.5 font-mono text-[0.92em] text-primary"
        >
          {part.slice(1, -1)}
        </code>
      );
    }
    return <span key={`${part}-${index}`}>{part}</span>;
  });
}

function answerCardClass(tone: OutputTone) {
  const base = "rounded-md border p-4";
  if (tone === "success") {
    return `${base} border-success/30 bg-success/5`;
  }
  if (tone === "warning") {
    return `${base} border-warning/30 bg-warning/5`;
  }
  if (tone === "danger") {
    return `${base} border-danger/30 bg-danger/5`;
  }
  if (tone === "info") {
    return `${base} border-primary/30 bg-primary/5`;
  }
  return `${base} border-border bg-muted/30`;
}

function answerIconClass(tone: OutputTone) {
  const base = "mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-md border";
  if (tone === "success") {
    return `${base} border-success/30 bg-success/10 text-success`;
  }
  if (tone === "warning") {
    return `${base} border-warning/30 bg-warning/10 text-warning`;
  }
  if (tone === "danger") {
    return `${base} border-danger/30 bg-danger/10 text-danger`;
  }
  if (tone === "info") {
    return `${base} border-primary/30 bg-primary/10 text-primary`;
  }
  return `${base} border-border bg-background text-muted-foreground`;
}

function answerLabelClass(tone: OutputTone) {
  const base = "rounded-sm border px-1.5 py-0.5 text-[10px] uppercase";
  if (tone === "success") {
    return `${base} border-success/30 bg-success/10 text-success`;
  }
  if (tone === "warning") {
    return `${base} border-warning/30 bg-warning/10 text-warning`;
  }
  if (tone === "danger") {
    return `${base} border-danger/30 bg-danger/10 text-danger`;
  }
  if (tone === "info") {
    return `${base} border-primary/30 bg-primary/10 text-primary`;
  }
  return `${base} border-border bg-background text-muted-foreground`;
}
