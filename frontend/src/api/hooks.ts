import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "./client";
import type { PostingFilter } from "./types";

export const keys = {
  postings: (f: PostingFilter) => ["postings", f] as const,
  posting: (id: number) => ["posting", id] as const,
  stats: ["stats"] as const,
  tags: ["tags"] as const,
  profile: ["profile"] as const,
  generators: ["generators"] as const,
  letters: (postingId: number) => ["letters", postingId] as const,
  letterContext: (postingId: number) => ["letter-context", postingId] as const,
  documents: ["documents"] as const,
  postingDocuments: (postingId: number) => ["posting-documents", postingId] as const,
};

export const usePostings = (f: PostingFilter) =>
  useQuery({ queryKey: keys.postings(f), queryFn: () => api.listPostings(f), placeholderData: keepPreviousData });

export const usePosting = (id: number | null) =>
  useQuery({ queryKey: keys.posting(id ?? -1), queryFn: () => api.getPosting(id!), enabled: id !== null });

export const useStats = () => useQuery({ queryKey: keys.stats, queryFn: api.stats });

export const useTags = () => useQuery({ queryKey: keys.tags, queryFn: api.tags, staleTime: 30_000 });

export const useProfile = () => useQuery({ queryKey: keys.profile, queryFn: api.profile });
export const useGenerators = () => useQuery({ queryKey: keys.generators, queryFn: api.generators, staleTime: 60_000 });
export const useLetters = (postingId: number) =>
  useQuery({ queryKey: keys.letters(postingId), queryFn: () => api.letters(postingId) });
export const useLetterContext = (postingId: number) =>
  useQuery({ queryKey: keys.letterContext(postingId), queryFn: () => api.letterContext(postingId) });

export const usePostingInsights = (postingId: number) =>
  useQuery({ queryKey: ["posting-insights", postingId], queryFn: () => api.postingInsights(postingId) });

export const useDocuments = () => useQuery({ queryKey: keys.documents, queryFn: api.documents });
export const usePostingDocuments = (postingId: number) =>
  useQuery({ queryKey: keys.postingDocuments(postingId), queryFn: () => api.postingDocuments(postingId) });

/** Jede Änderung macht Listen, Detail und Kennzahlen ungültig: einfach und immer konsistent. */
export function useMutate<TArgs, TResult>(fn: (args: TArgs) => Promise<TResult>) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["postings"] });
      void qc.invalidateQueries({ queryKey: ["posting"] });
      void qc.invalidateQueries({ queryKey: keys.stats });
      void qc.invalidateQueries({ queryKey: keys.tags });
      void qc.invalidateQueries({ queryKey: ["letters"] });
      void qc.invalidateQueries({ queryKey: ["letter-context"] });
      void qc.invalidateQueries({ queryKey: keys.profile });
      void qc.invalidateQueries({ queryKey: keys.documents });
      void qc.invalidateQueries({ queryKey: ["posting-documents"] });
      void qc.invalidateQueries({ queryKey: ["posting-insights"] });
    },
  });
}
