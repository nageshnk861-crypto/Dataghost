type Classification = "PUBLIC" | "INTERNAL" | "CONFIDENTIAL" | "RESTRICTED";

interface ClassificationBadgeProps {
  classification: Classification;
}

const CONFIG: Record<Classification, { bg: string; text: string; border: string }> = {
  PUBLIC: {
    bg: "rgba(52,208,88,0.1)",
    text: "#34d058",
    border: "rgba(52,208,88,0.25)",
  },
  INTERNAL: {
    bg: "rgba(0,112,255,0.1)",
    text: "#60a5fa",
    border: "rgba(96,165,250,0.25)",
  },
  CONFIDENTIAL: {
    bg: "rgba(255,159,10,0.1)",
    text: "#ff9f0a",
    border: "rgba(255,159,10,0.25)",
  },
  RESTRICTED: {
    bg: "rgba(255,59,59,0.1)",
    text: "#ff3b3b",
    border: "rgba(255,59,59,0.25)",
  },
};

export default function ClassificationBadge({ classification }: ClassificationBadgeProps) {
  const cfg = CONFIG[classification] ?? CONFIG.PUBLIC;
  return (
    <span
      className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold tracking-wide uppercase"
      style={{
        background: cfg.bg,
        color: cfg.text,
        border: `1px solid ${cfg.border}`,
      }}
    >
      {classification}
    </span>
  );
}
