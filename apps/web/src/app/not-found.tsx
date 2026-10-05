import Link from "next/link";
import { EmptyState } from "@/components/ui";

export default function NotFound() {
  return (
    <EmptyState title="Page not found" action={<Link href="/" className="btn">Back to the watchlist</Link>}>
      That address does not match anything in aTrader.
    </EmptyState>
  );
}
