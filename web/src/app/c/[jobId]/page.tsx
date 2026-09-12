import { PublicCatalogClient } from "./PublicCatalogClient";

export default async function PublicCatalogPage(props: PageProps<"/c/[jobId]">) {
  const { jobId } = await props.params;
  return <PublicCatalogClient jobId={jobId} />;
}
