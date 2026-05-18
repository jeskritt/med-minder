/**
 * Interaction-rule helpers (Phase 6 / US3).
 *
 * Create + delete only — no update path (the clarified scope is
 * delete-then-recreate). The medication form orchestrates persistence
 * (medications.new / medications.$id.edit); these are thin wrappers
 * over the generated client plus a preload query for the edit page.
 */

import { useQuery } from "@tanstack/react-query";
import { client } from "@/lib/api";
import type { components } from "@/api/v1";

export type InteractionRuleOut = components["schemas"]["InteractionRuleOut"];

export function medicationRulesKey(medicationId: string) {
  return ["medication-interactions", medicationId] as const;
}

export async function listInteractionRules(
  medicationId: string,
): Promise<InteractionRuleOut[]> {
  const { data, error } = await client.GET(
    "/api/v1/medications/{medication_id}/interactions",
    { params: { path: { medication_id: medicationId } } },
  );
  if (error || !data) throw new Error("Failed to load interaction rules");
  return data;
}

export async function createInteractionRule(
  medicationId: string,
  body: { other_medication_id: string; cooldown_minutes: number },
): Promise<void> {
  const { error, response } = await client.POST(
    "/api/v1/medications/{medication_id}/interactions",
    { params: { path: { medication_id: medicationId } }, body },
  );
  if (error) {
    throw new Error(
      response.status === 409
        ? "An interaction rule for that pair already exists."
        : response.status === 422
          ? "Invalid interaction (self-pair or non-positive cooldown)."
          : "Failed to create interaction rule.",
    );
  }
}

export async function deleteInteractionRule(
  medicationId: string,
  interactionId: string,
): Promise<void> {
  const { error } = await client.DELETE(
    "/api/v1/medications/{medication_id}/interactions/{interaction_id}",
    {
      params: {
        path: {
          medication_id: medicationId,
          interaction_id: interactionId,
        },
      },
    },
  );
  if (error) throw new Error("Failed to remove interaction rule.");
}

/** Preload existing rules for the edit form. */
export function useMedicationRules(medicationId: string | undefined) {
  return useQuery({
    queryKey: medicationRulesKey(medicationId ?? ""),
    queryFn: () => listInteractionRules(medicationId as string),
    enabled: medicationId !== undefined,
  });
}
