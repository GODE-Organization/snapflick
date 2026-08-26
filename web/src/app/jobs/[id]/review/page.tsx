import { ReviewClient } from "./ReviewClient";

export default async function ReviewPage(props: PageProps<"/jobs/[id]/review">) {
  const { id } = await props.params;
  return <ReviewClient jobId={id} />;
}
