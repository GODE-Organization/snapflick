import { CatalogClient } from "./CatalogClient";

export default async function CatalogPage(props: PageProps<"/jobs/[id]/catalog">) {
  const { id } = await props.params;
  return <CatalogClient jobId={id} />;
}
