import type { Metadata } from "next";
import { WatchlistView } from "@/components/views/watchlist-view";

export const metadata: Metadata = { title: "Watchlist" };

export default function Page() {
  return <WatchlistView />;
}
