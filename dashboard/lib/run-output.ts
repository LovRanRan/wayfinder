import {
  AlertTriangle,
  Code2,
  FileText,
  ListChecks,
  Network,
  ShieldCheck,
  Terminal,
} from "lucide-react";

export type OutputTone = "muted" | "success" | "warning" | "danger" | "info";

export type OutputBlock = {
  label: string;
  title: string;
  body: string;
  tone: OutputTone;
  icon: typeof Terminal;
};

export function outputBlocksFromText(output: string): OutputBlock[] {
  const paragraphs = mergeHeadingParagraphs(
    output
      .split(/\n{2,}/)
      .map((paragraph) => paragraph.trim())
      .filter(Boolean),
  );

  if (paragraphs.length === 0) {
    return [
      {
        label: "output",
        title: "Output",
        body: "No answer content was returned.",
        tone: "muted",
        icon: FileText,
      },
    ];
  }

  return paragraphs.map(outputBlockFromParagraph);
}

function mergeHeadingParagraphs(paragraphs: string[]) {
  const merged: string[] = [];
  for (let index = 0; index < paragraphs.length; index += 1) {
    const paragraph = paragraphs[index];
    const next = paragraphs[index + 1];
    if (next && isStandaloneHeading(paragraph)) {
      merged.push(`${paragraph}\n${next}`);
      index += 1;
    } else {
      merged.push(paragraph);
    }
  }
  return merged;
}

function isStandaloneHeading(paragraph: string) {
  const lines = paragraph.split("\n");
  return lines.length === 1 && paragraph.length <= 90 && /:\s*$/.test(paragraph);
}

function outputBlockFromParagraph(paragraph: string): OutputBlock {
  const lines = paragraph.split("\n");
  const firstLine = lines[0]?.trim() ?? "";
  const hasHeading = isStandaloneHeading(firstLine) && lines.length > 1;
  const explicitTitle = hasHeading ? titleFromHeading(firstLine) : null;
  const body = hasHeading ? lines.slice(1).join("\n").trim() : paragraph;
  const searchable = `${explicitTitle ?? ""}\n${body}`.toLowerCase();

  if (searchable.includes("verification summary")) {
    return block("verification", explicitTitle ?? "Verification summary", body, "warning", ListChecks);
  }

  if (searchable.includes("contradicted") || searchable.includes("contradiction")) {
    return block("contradiction", explicitTitle ?? "Contradiction", body, "danger", AlertTriangle);
  }

  if (
    searchable.includes("unverified") ||
    searchable.includes("limitation") ||
    searchable.includes("uncertainty") ||
    searchable.includes("cannot") ||
    searchable.includes("no test") ||
    searchable.includes("scan failed")
  ) {
    return block("limitation", explicitTitle ?? "Limitations and uncertainty", body, "warning", AlertTriangle);
  }

  if (
    searchable.includes("verified from ast") ||
    searchable.includes("source citations") ||
    searchable.includes("signature") ||
    searchable.includes("defined in")
  ) {
    return block("evidence", explicitTitle ?? "Verified evidence", body, "success", ShieldCheck);
  }

  if (
    searchable.includes("control-flow") ||
    searchable.includes("data flow") ||
    searchable.includes("architecture path") ||
    searchable.includes("entry explanation path") ||
    searchable.includes("verifier path")
  ) {
    return block("flow", explicitTitle ?? "Observed flow", body, "info", Network);
  }

  if (searchable.includes("behavior") || searchable.includes("function body")) {
    return block("behavior", explicitTitle ?? "Behavior", body, "muted", Code2);
  }

  if (searchable.includes("recommended") || searchable.includes("suggested")) {
    return block("next step", explicitTitle ?? "Recommended next step", body, "info", ListChecks);
  }

  return block("answer", explicitTitle ?? "Answer", body, "muted", FileText);
}

function block(
  label: string,
  title: string,
  body: string,
  tone: OutputTone,
  icon: typeof Terminal,
): OutputBlock {
  return {
    label,
    title,
    body: body.trim() || title,
    tone,
    icon,
  };
}

function titleFromHeading(heading: string) {
  return heading.replace(/:\s*$/, "").trim();
}
