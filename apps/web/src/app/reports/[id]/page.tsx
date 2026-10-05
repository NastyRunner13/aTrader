import { ReportPage } from "@/components/views/report-page";

export default async function Page({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <ReportPage id={id} />;
}
