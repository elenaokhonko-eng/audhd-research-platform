import { cleanSlug } from "@/lib/slug";
import { JoinPage } from "../JoinPage";

export const dynamic = "force-dynamic";

export default async function Page({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  return <JoinPage slug={cleanSlug(slug)} />;
}
