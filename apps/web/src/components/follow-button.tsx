"use client";

import { Star } from "lucide-react";
import { useSWRConfig } from "swr";
import { api } from "@/lib/api";
import { useAction, useApi } from "@/lib/hooks";
import type { WatchlistItem } from "@/lib/types";

export function FollowButton({ symbol }: { symbol: string }) {
  const { mutate } = useSWRConfig();
  const { data } = useApi<WatchlistItem[]>("/v1/watchlist");
  const toggle = useAction(async (follow: boolean) => {
    if (follow) await api.follow(symbol);
    else await api.unfollow(symbol);
    await mutate("/v1/watchlist");
  });
  const following = data?.some((item) => item.symbol === symbol) ?? false;
  return (
    <button
      type="button"
      className="btn"
      aria-pressed={following}
      disabled={data === undefined || toggle.pending}
      onClick={() => void toggle.run(!following)}
      title={following ? "Remove from the watchlist" : "Add to the watchlist"}
    >
      <Star size={15} aria-hidden fill={following ? "currentColor" : "none"} className={following ? "text-accent" : ""} />
      {following ? "Following" : "Follow"}
    </button>
  );
}
