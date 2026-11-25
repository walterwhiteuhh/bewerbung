import { useEntityTags, useSetEntityTags } from "../api/hooks";
import type { EntityType } from "../api/types";
import { TagInput } from "./TagInput";
import { useToast } from "./Toast";

/** Hashtags an Firma, Unterlage oder gespeicherter Suche: dieselben Tags wie bei Stellen. */
export function EntityTags({ type, id, placeholder }: { type: EntityType; id: number; placeholder?: string }) {
  const toast = useToast();
  const { data } = useEntityTags(type);
  const set = useSetEntityTags(type);
  const value = data?.[String(id)] ?? [];
  return (
    <TagInput
      value={value}
      placeholder={placeholder}
      onChange={(tags) => set.mutate({ id, tags }, { onError: (e) => toast(e.message, "error") })}
    />
  );
}
