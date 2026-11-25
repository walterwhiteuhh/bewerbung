import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "./client";
import type { EntityType, PostingFilter } from "./types";

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

export const usePostingInsights = (postingId: number, enabled = true) =>
  useQuery({ queryKey: ["posting-insights", postingId], queryFn: () => api.postingInsights(postingId), enabled });

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

/** Hashtags aller Objekte eines Typs (ein Abruf für die ganze Liste). */
export const useEntityTags = (type: EntityType) =>
  useQuery({ queryKey: ["tag-links", type], queryFn: () => api.entityTags(type), staleTime: 15_000 });

export function useSetEntityTags(type: EntityType) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, tags }: { id: number; tags: string[] }) => api.setEntityTags(type, id, tags),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["tag-links", type] });
      void qc.invalidateQueries({ queryKey: keys.tags });
    },
  });
}

/** Alles zu einem Hashtag; 404 (Tag unbekannt) ist kein Fehler, dann gibt es einfach nichts. */
export const useTagOverview = (name: string | null) =>
  useQuery({ queryKey: ["tag-overview", name], queryFn: () => api.tagOverview(name!), enabled: !!name, retry: false, staleTime: 30_000 });
