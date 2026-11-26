/** The four sections, shared by the header (client) and the footer (server). */
export const NAV = [
  { href: "/", label: "Search" },
  { href: "/lifestyle", label: "Lifestyle match" },
  { href: "/neighborhoods", label: "Neighbourhoods" },
  { href: "/rent-check", label: "Rent check" },
] as const;

/** Which section a path belongs to (listing pages belong to Search). */
export function isActive(href: string, pathname: string): boolean {
  if (href === "/") return pathname === "/" || pathname.startsWith("/listings");
  return pathname.startsWith(href);
}
