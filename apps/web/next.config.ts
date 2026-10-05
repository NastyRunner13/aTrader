import type { NextConfig } from "next";

const config: NextConfig = {
  reactStrictMode: true,
  // The UI talks to the local aTrader API directly (CORS allows localhost:3000).
  // Build output stays in .next, which is a junction outside OneDrive on this machine.
  poweredByHeader: false,
};

export default config;
