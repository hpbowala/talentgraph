import type { MouseEvent } from "react";

/**
 * Feeds cursor coordinates to the `.spot` radial-glow pseudo-element as
 * CSS custom properties, so the highlight follows the mouse.
 */
export function trackSpotlight(e: MouseEvent<HTMLElement>) {
  const rect = e.currentTarget.getBoundingClientRect();
  e.currentTarget.style.setProperty("--mx", `${e.clientX - rect.left}px`);
  e.currentTarget.style.setProperty("--my", `${e.clientY - rect.top}px`);
}
