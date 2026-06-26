"use client";

import { useState } from "react";

type Fit = "contain" | "cover";

export function SpeciesImage({
  src,
  alt,
  fit = "contain",
}: {
  src: string;
  alt: string;
  fit?: Fit;
}) {
  const [failed, setFailed] = useState(false);

  if (failed) {
    // Soft fallback: a neutral placeholder square so the row layout
    // stays intact when Ensembl/Wikipedia rejects the request.
    return (
      <span
        aria-hidden
        className="flex h-full w-full items-center justify-center bg-paper text-foreground/30"
      >
        <svg viewBox="0 0 24 24" className="size-6" fill="none" stroke="currentColor" strokeWidth="1.5">
          <circle cx="12" cy="12" r="9" />
          <path d="M8 14c.667.667 2 2 4 2s3.333-1.333 4-2" />
          <circle cx="9" cy="10" r="1" fill="currentColor" />
          <circle cx="15" cy="10" r="1" fill="currentColor" />
        </svg>
      </span>
    );
  }

  return (
    <img
      src={src}
      alt={alt}
      loading="lazy"
      onError={() => setFailed(true)}
      className={
        fit === "cover"
          ? "h-full w-full object-cover"
          : "h-full w-full object-contain"
      }
    />
  );
}
