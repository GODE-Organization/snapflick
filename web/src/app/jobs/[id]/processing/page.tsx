import { ProcessingClient } from "./ProcessingClient";

export default async function ProcessingPage(props: PageProps<"/jobs/[id]/processing">) {
  const { id } = await props.params;
  return <ProcessingClient jobId={id} />;
}
