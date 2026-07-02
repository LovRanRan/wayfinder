import { PageSkeleton } from "@/components/ui/skeleton";

export default function Loading() {
  return (
    <div className="mx-auto max-w-5xl px-4 py-6 md:px-6">
      <PageSkeleton />
    </div>
  );
}
