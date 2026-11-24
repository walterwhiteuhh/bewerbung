import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "./client";
import type { PostingFilter } from "./types";

export const keys = {
  postings: (f: PostingFilter) => ["postings", f] as const,
  posting: (id: number) => ["posting", id] as const,
  stats: ["stats"] as const,
};

export const usePostings = (f: PostingFilter) =>
  useQuery({ queryKey: keys.postings(f), queryFn: () => api.listPostings(f), placeholderData: keepPreviousData });

export const usePosting = (id: number | null) =>
  useQuery({ queryKey: keys.posting(id ?? -1), queryFn: () => api.getPosting(id!), enabled: id !== null });

export const useStats = () => useQuery({ queryKey: keys.stats, queryFn: api.stats });

/** Jede Änderung macht Listen, Detail und Kennzahlen ungültig: einfach und immer konsistent. */
export function useMutate<TArgs, TResult>(fn: (args: TArgs) => Promise<TResult>) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["postings"] });
      void qc.invalidateQueries({ queryKey: ["posting"] });
      void qc.invalidateQueries({ queryKey: keys.stats });
    },
  });
}
