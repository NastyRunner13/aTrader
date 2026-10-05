import { CompanyView } from "@/components/views/company-view";

export default async function Page({ params }: { params: Promise<{ symbol: string }> }) {
  const { symbol } = await params;
  return <CompanyView symbol={decodeURIComponent(symbol).toUpperCase()} />;
}
