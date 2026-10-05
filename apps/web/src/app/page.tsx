import type { Metadata } from "next";
import { WatchlistView } from "@/components/views/watchlist-view";

export const metadata: Metadata = { title: "Overview" };

export default function Page() {
  return <WatchlistView />;
}
